import socket
import json
import os
import pickle
import struct
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QListWidget, 
                            QTextEdit, QGroupBox, QLineEdit, QDialog,
                            QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QUrl, QSize, QThread
from PyQt5.QtGui import QPixmap, QImage, QTextDocument, QIcon, QFont
import time
import uuid
from wuzi_game import WuziWindow

# 添加全局样式表
STYLE_SHEET = """
QMainWindow {
    background-color: #f0f2f5;
}

QGroupBox {
    border: 2px solid #dcdfe6;
    border-radius: 6px;
    margin-top: 1em;
    font-size: 14px;
    background-color: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #409eff;
}

QPushButton {
    background-color: #409eff;
    color: white;
    border: none;
    padding: 5px 15px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #66b1ff;
}

QPushButton:pressed {
    background-color: #3a8ee6;
}

QLineEdit {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 5px;
    font-size: 13px;
    min-height: 25px;
}

QLineEdit:focus {
    border-color: #409eff;
}

QTextEdit {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 5px;
    font-size: 13px;
    background-color: white;
}

QListWidget {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 5px;
    font-size: 13px;
    background-color: white;
}

QListWidget::item {
    padding: 5px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #ecf5ff;
    color: #409eff;
}

QListWidget::item:hover {
    background-color: #f5f7fa;
}
"""

class SignalManager(QObject):
    """信号管理器，用于线程间通信"""
    display_message = pyqtSignal(str)
    display_image = pyqtSignal(QImage)
    update_users = pyqtSignal(list)
    update_files = pyqtSignal(list)
    connection_lost = pyqtSignal()
    force_logout = pyqtSignal()
    create_game = pyqtSignal(str, bool)  # 添加创建游戏窗口的信号
    handle_game_action = pyqtSignal(dict)  # 添加处理游戏动作的信号

class NetworkThread(QThread):
    """网络通信线程"""
    message_received = pyqtSignal(bytes, bytes)  # 接收到的消息信号
    connection_lost = pyqtSignal()  # 连接断开信号
    
    def __init__(self, socket):
        super().__init__()
        self.socket = socket
        self.running = True
        
    def run(self):
        while self.running:
            try:
                type_flag = self.socket.recv(1)
                if not type_flag:
                    break
                    
                if type_flag in [b'\x01', b'\x02']:  # 表情或文件消息
                    length_data = self.socket.recv(4)
                    if not length_data:
                        break
                    msg_length = struct.unpack('>I', length_data)[0]
                    
                    data = b''
                    while len(data) < msg_length:
                        chunk = self.socket.recv(min(msg_length - len(data), 8192))
                        if not chunk:
                            break
                        data += chunk
                    
                    if len(data) == msg_length:
                        self.message_received.emit(type_flag, data)
                else:  # 普通消息
                    message = self.socket.recv(8191)
                    if not message:
                        break
                    self.message_received.emit(type_flag, message)
                    
            except Exception as e:
                print(f"接收消息错误: {str(e)}")
                break
                
        self.running = False
        self.connection_lost.emit()
        
    def stop(self):
        self.running = False

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setStyleSheet(STYLE_SHEET)
        
    def setup_ui(self):
        self.setWindowTitle("登录")
        self.setFixedSize(320, 200)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("欢迎登录")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; color: #303133; margin-bottom: 20px;")
        layout.addWidget(title_label)
        
        # 用户名输入
        self.username_label = QLabel("用户名:")
        self.username_label.setStyleSheet("color: #606266;")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        
        # 登录按钮
        self.login_button = QPushButton("登录")
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #409eff;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
        """)
        self.login_button.clicked.connect(self.accept)
        layout.addWidget(self.login_button)
        
        self.setLayout(layout)
        
    def get_username(self):
        return self.username_input.text().strip()

class EmojiSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_emoji = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("选择表情")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # 创建表情网格
        self.emoji_grid = QWidget()
        grid_layout = QHBoxLayout()
        self.emoji_grid.setLayout(grid_layout)
        
        # 加载表情
        emoji_dir = "emojis"
        if not os.path.exists(emoji_dir):
            os.makedirs(emoji_dir)
            
        for file in os.listdir(emoji_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                try:
                    image_path = os.path.join(emoji_dir, file)
                    button = QPushButton()
                    icon = QIcon(image_path)  # 直接从文件路径创建QIcon
                    button.setIcon(icon)
                    button.setIconSize(QSize(40, 40))  # 设置图标大小
                    button.setFixedSize(50, 50)
                    button.clicked.connect(lambda checked, f=file: self.select_emoji(f))
                    grid_layout.addWidget(button)
                except Exception as e:
                    print(f"加载表情失败: {file}, 错误: {str(e)}")
                    
        layout.addWidget(self.emoji_grid)
        self.setLayout(layout)
        
    def select_emoji(self, emoji_file):
        self.selected_emoji = os.path.join("emojis", emoji_file)
        self.accept()

class ChatClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_network()
        self.setup_gui()
        self.setStyleSheet(STYLE_SHEET)
        
        # 创建信号管理器
        self.signals = SignalManager()
        self.signals.display_message.connect(self.append_message, Qt.QueuedConnection)
        self.signals.display_image.connect(self.append_image, Qt.QueuedConnection)
        self.signals.update_users.connect(self.update_users_gui, Qt.QueuedConnection)
        self.signals.update_files.connect(self.update_files_gui, Qt.QueuedConnection)
        self.signals.connection_lost.connect(self.handle_disconnect, Qt.QueuedConnection)
        self.signals.force_logout.connect(self.handle_force_logout, Qt.QueuedConnection)
        self.signals.create_game.connect(self.create_game_window, Qt.QueuedConnection)
        self.signals.handle_game_action.connect(self.process_game_action, Qt.QueuedConnection)
        
        # 游戏相关
        self.game_window = None
        
    def setup_network(self):
        self.host = 'localhost'
        self.port = 5000
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def setup_gui(self):
        self.setWindowTitle("聊天客户端")
        self.setGeometry(100, 100, 1000, 700)  # 调整窗口大小
        
        # 创建主窗口部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 左侧聊天区域
        chat_group = QGroupBox("聊天区域")
        chat_layout = QVBoxLayout()
        chat_layout.setSpacing(10)
        
        # 聊天记录显示
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        chat_layout.addWidget(self.chat_area)
        
        # 消息输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.returnPressed.connect(self.send_message)
        
        self.send_button = QPushButton("发送")
        self.send_button.setIcon(QIcon("emojis/icons8-书呆子-80.png"))
        self.send_button.clicked.connect(self.send_message)
        
        self.file_button = QPushButton("发送文件")
        self.file_button.setIcon(QIcon("emojis/icons8-宣誓的男性-80.png"))
        self.file_button.clicked.connect(self.send_file_dialog)
        
        self.emoji_button = QPushButton("发送表情")
        self.emoji_button.setIcon(QIcon("emojis/icons8-伸出舌头-80.png"))
        self.emoji_button.clicked.connect(self.show_emoji_selector)
        
        # 添加游戏按钮
        self.game_button = QPushButton("邀请对战")
        self.game_button.setIcon(QIcon("emojis/icons8-灵活的二头肌-80.png"))
        self.game_button.clicked.connect(self.invite_game)
        
        input_layout.addWidget(self.message_input, stretch=3)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.file_button)
        input_layout.addWidget(self.emoji_button)
        input_layout.addWidget(self.game_button)
        
        chat_layout.addLayout(input_layout)
        chat_group.setLayout(chat_layout)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        # 在线用户列表
        users_group = QGroupBox("在线用户")
        users_layout = QVBoxLayout()
        self.users_list = QListWidget()
        users_layout.addWidget(self.users_list)
        users_group.setLayout(users_layout)
        
        # 服务器文件列表
        files_group = QGroupBox("服务器文件")
        files_layout = QVBoxLayout()
        self.files_list = QListWidget()
        self.download_button = QPushButton("下载选中文件")
        self.download_button.setIcon(QIcon("emojis/icons8-剑-80.png"))
        self.download_button.clicked.connect(self.download_file)
        files_layout.addWidget(self.files_list)
        files_layout.addWidget(self.download_button)
        files_group.setLayout(files_layout)
        
        right_layout.addWidget(users_group)
        right_layout.addWidget(files_group)
        right_panel.setLayout(right_layout)
        
        # 添加到主布局
        layout.addWidget(chat_group, stretch=2)
        layout.addWidget(right_panel, stretch=1)
        
    def append_message(self, message):
        """添加文本消息到聊天区域"""
        self.chat_area.append(message)
        
    def append_image(self, qimage):
        """添加图片到聊天区域"""
        cursor = self.chat_area.textCursor()
        cursor.movePosition(cursor.End)
        
        # 使用时间戳和随机数生成唯一的资源名称
        resource_name = f"emoji_{time.time()}_{uuid.uuid4().hex[:8]}.png"
        
        pixmap = QPixmap.fromImage(qimage)
        self.chat_area.document().addResource(
            QTextDocument.ImageResource,
            QUrl(resource_name),
            pixmap
        )
        cursor.insertImage(resource_name)
        cursor.insertText("\n")
        
    def update_users_gui(self, users):
        """更新用户列表"""
        self.users_list.clear()
        self.users_list.addItem("所有人")
        self.users_list.setCurrentRow(0)  # 默认选中"所有人"
        for user in users:
            if user != self.username:
                self.users_list.addItem(user)
                
    def update_files_gui(self, files):
        """更新文件列表"""
        self.files_list.clear()
        self.files_list.addItems(files)
        
    def show_emoji_selector(self):
        selector = EmojiSelector(self)
        if selector.exec_() == QDialog.Accepted and selector.selected_emoji:
            self.send_emoji(selector.selected_emoji)
            
    def send_message(self):
        message = self.message_input.text().strip()
        if message:
            selected_items = self.users_list.selectedItems()
            to = selected_items[0].text() if selected_items else "所有人"
            
            data = {
                'type': 'message',
                'content': message,
                'to': to
            }
            
            try:
                self.client_socket.send(json.dumps(data).encode())
                self.message_input.clear()
                if to == "所有人":
                    self.signals.display_message.emit(f"你: {message}")
                else:
                    self.signals.display_message.emit(f"你对{to}说: {message}")
            except:
                QMessageBox.critical(self, "错误", "消息发送失败")
                
    def send_emoji(self, emoji_path):
        try:
            selected_items = self.users_list.selectedItems()
            to = selected_items[0].text() if selected_items else "所有人"
            
            with open(emoji_path, 'rb') as f:
                image_data = f.read()
                
            emoji_data = {
                'type': 'emoji',
                'to': to,
                'image': image_data
            }
            
            data = pickle.dumps(emoji_data)
            self.client_socket.send(b'\x01')
            self.client_socket.send(struct.pack('>I', len(data)))
            self.client_socket.send(data)
            
            # 显示发送的表情
            qimage = QImage(emoji_path)
            if to == "所有人":
                self.signals.display_message.emit("你: ")
            else:
                self.signals.display_message.emit(f"你对{to}说: ")
            self.signals.display_image.emit(qimage)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送表情失败: {str(e)}")
            
    def send_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            selected_items = self.users_list.selectedItems()
            to = selected_items[0].text() if selected_items else "所有人"
            
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    
                file_package = {
                    'type': 'file',
                    'filename': os.path.basename(file_path),
                    'to': to,
                    'content': file_data
                }
                
                data = pickle.dumps(file_package)
                self.client_socket.send(b'\x02')
                self.client_socket.send(struct.pack('>I', len(data)))
                
                chunk_size = 8192
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i + chunk_size]
                    self.client_socket.send(chunk)
                    
                self.signals.display_message.emit(f"文件 {os.path.basename(file_path)} 发送完成")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"文件发送失败: {str(e)}")
                
    def download_file(self):
        if not self.files_list.selectedItems():
            QMessageBox.warning(self, "提示", "请先选择要下载的文件")
            return
            
        filename = self.files_list.currentItem().text()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            filename,
            "All Files (*.*)"
        )
        
        if save_path:
            download_request = {
                'type': 'file',
                'action': 'download',
                'filename': filename,
                'save_path': save_path
            }
            
            try:
                data = pickle.dumps(download_request)
                self.client_socket.send(b'\x02')
                self.client_socket.send(struct.pack('>I', len(data)))
                self.client_socket.send(data)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"发送下载请求失败: {str(e)}")
                
    def connect_to_server(self, username):
        try:
            self.client_socket.connect((self.host, self.port))
            self.username = username
            self.client_socket.send(username.encode())
            
            # 创建并启动网络线程
            self.network_thread = NetworkThread(self.client_socket)
            self.network_thread.message_received.connect(self.handle_message, Qt.QueuedConnection)
            self.network_thread.connection_lost.connect(self.handle_disconnect, Qt.QueuedConnection)
            self.network_thread.start()
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"无法连接到服务器: {str(e)}")
            return False
            
    def handle_message(self, type_flag, message):
        """处理接收到的消息"""
        try:
            if type_flag == b'\x01':  # 表情消息
                emoji_data = pickle.loads(message)
                image_data = emoji_data['image']
                qimage = QImage()
                qimage.loadFromData(image_data)
                
                if emoji_data.get('from'):
                    self.signals.display_message.emit(f"{emoji_data['from']}对你说: ")
                self.signals.display_image.emit(qimage)
                
            elif type_flag == b'\x02':  # 文件消息
                file_data = pickle.loads(message)
                if 'save_path' in file_data:  # 这是下载的响应
                    try:
                        with open(file_data['save_path'], 'wb') as f:
                            f.write(file_data['content'])
                        self.signals.display_message.emit(
                            f"文件已保存到: {file_data['save_path']}"
                        )
                    except Exception as e:
                        self.signals.display_message.emit(
                            f"保存文件失败: {str(e)}"
                        )
                else:  # 这是接收到的文件
                    try:
                        save_path = file_data.get('save_path', file_data['filename'])
                        with open(save_path, 'wb') as f:
                            f.write(file_data['content'])
                        if file_data.get('from'):
                            self.signals.display_message.emit(
                                f"收到来自 {file_data['from']} 的文件: {file_data['filename']}"
                            )
                        else:
                            self.signals.display_message.emit(
                                f"文件 {os.path.basename(save_path)} 下载完成"
                            )
                    except Exception as e:
                        self.signals.display_message.emit(
                            f"保存文件失败: {str(e)}"
                        )
                        
            else:  # 普通消息
                try:
                    data = json.loads((type_flag + message).decode())
                    if isinstance(data, dict):
                        if data['type'] == 'game_invite':
                            self.handle_game_invite(data['from'])
                        elif data['type'] == 'game_invite_response':
                            self.handle_game_invite_response(data['from'], data['accepted'])
                        elif data['type'] == 'game_move':
                            self.handle_game_move(data)
                        elif data['type'] == 'private_message':
                            self.signals.display_message.emit(
                                f"{data['from']}对你说: {data['content']}"
                            )
                        elif data['type'] == 'users_list':
                            self.signals.update_users.emit(data['users'])
                        elif data['type'] == 'files_list':
                            self.signals.update_files.emit(data['files'])
                        elif data['type'] == 'server_message':
                            self.signals.display_message.emit(f"SERVER: {data['content']}")
                            if data['content'] == '您已被服务器强制下线':
                                self.signals.force_logout.emit()
                        elif data['type'] == 'message':
                            self.signals.display_message.emit(
                                f"{data['from']}: {data['content']}"
                            )
                    else:
                        self.signals.display_message.emit((type_flag + message).decode())
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {str(e)}, 消息内容: {(type_flag + message).decode()}")
                    
        except Exception as e:
            print(f"处理消息错误: {str(e)}")
            
    def handle_force_logout(self):
        """处理强制下线"""
        QMessageBox.warning(self, "强制下线", "您已被服务器强制下线")
        self.close()
        
    def handle_disconnect(self):
        """处理连接断开"""
        QMessageBox.warning(self, "连接断开", "与服务器的连接已断开")
        self.close()
        
    def invite_game(self):
        """发送游戏邀请"""
        if not self.users_list.selectedItems() or self.users_list.currentItem().text() == "所有人":
            QMessageBox.warning(self, "提示", "请先选择一个在线用户")
            return
            
        opponent = self.users_list.currentItem().text()
        
        # 发送游戏邀请
        invite_data = {
            'type': 'game_invite',
            'to': opponent
        }
        
        try:
            self.client_socket.send(json.dumps(invite_data).encode())
            self.signals.display_message.emit(f"已向 {opponent} 发送游戏邀请")
        except:
            QMessageBox.critical(self, "错误", "发送游戏邀请失败")
            
    def create_game_window(self, opponent, is_black):
        """在主线程中创建游戏窗口"""
        try:
            if self.game_window:
                try:
                    self.game_window.close()
                except:
                    pass
            
            self.game_window = WuziWindow(self.username, opponent, is_black)
            self.game_window.game_move.connect(self.send_game_move)
            self.game_window.show()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建游戏窗口失败: {str(e)}")

    def process_game_action(self, data):
        """在主线程中处理游戏动作"""
        try:
            if not self.game_window:
                return
                
            action = data.get('action')
            
            if action == 'move':
                x = data.get('x')
                y = data.get('y')
                if x is not None and y is not None:
                    self.game_window.on_opponent_move(x, y)
            elif action == 'win':
                # 对手宣布获胜，说明我们输了
                QMessageBox.information(self, "游戏结束", "你输了！")
                self.game_window.board.is_game_over = True
                self.game_window.update_status_label()
            elif action == 'surrender':
                # 对手认输，我们获胜
                QMessageBox.information(self, "游戏结束", "对手认输，你获胜了！")
                self.game_window.board.is_game_over = True
                self.game_window.update_status_label()
            elif action == 'draw_request':
                reply = QMessageBox.question(self, "求和请求", 
                                           "对手请求和棋，是否同意？",
                                           QMessageBox.Yes | QMessageBox.No)
                
                response_data = {
                    'type': 'game_move',
                    'action': 'draw_response',
                    'accepted': reply == QMessageBox.Yes,
                    'to': self.game_window.opponent
                }
                self.send_game_move(response_data)
                
                if reply == QMessageBox.Yes:
                    QMessageBox.information(self, "游戏结束", "双方同意和棋！")
                    self.game_window.board.is_game_over = True
                    self.game_window.update_status_label()
            elif action == 'draw_response':
                self.game_window.handle_draw_response(data.get('accepted', False))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理游戏动作失败: {str(e)}")
            if self.game_window:
                self.game_window.close()

    def handle_game_invite(self, from_user):
        """处理收到的游戏邀请"""
        try:
            reply = QMessageBox.question(self, "游戏邀请", 
                                       f"{from_user} 邀请你进行五子棋对战，是否接受？",
                                       QMessageBox.Yes | QMessageBox.No)
            
            response_data = {
                'type': 'game_invite_response',
                'to': from_user,
                'accepted': reply == QMessageBox.Yes
            }
            
            try:
                self.client_socket.send(json.dumps(response_data).encode())
                
                if reply == QMessageBox.Yes:
                    # 通过信号创建游戏窗口（作为白方）
                    self.signals.create_game.emit(from_user, False)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"发送响应失败: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理游戏邀请失败: {str(e)}")
            
    def handle_game_invite_response(self, from_user, accepted):
        """处理游戏邀请的响应"""
        try:
            if accepted:
                self.signals.display_message.emit(f"{from_user} 接受了游戏邀请")
                # 通过信号创建游戏窗口（作为黑方）
                self.signals.create_game.emit(from_user, True)
            else:
                self.signals.display_message.emit(f"{from_user} 拒绝了游戏邀请")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理游戏邀请响应失败: {str(e)}")
            
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            # 先关闭游戏窗口（如果存在）
            if self.game_window:
                try:
                    self.game_window.close()
                    self.game_window = None
                except:
                    pass

            # 停止网络线程
            if hasattr(self, 'network_thread'):
                self.network_thread.running = False
                self.network_thread.quit()
                self.network_thread.wait(1000)  # 最多等待1秒
                if self.network_thread.isRunning():
                    self.network_thread.terminate()

            # 关闭socket连接
            if hasattr(self, 'client_socket'):
                try:
                    self.client_socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.client_socket.close()
                except:
                    pass

            event.accept()
        except Exception as e:
            print(f"关闭窗口错误: {str(e)}")
            event.accept()
        
    def start(self):
        # 显示登录对话框
        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            username = login_dialog.get_username()
            if username:
                if self.connect_to_server(username):
                    self.show()
                else:
                    self.close()
            else:
                QMessageBox.warning(self, "提示", "请输入用户名")
                self.close()
        else:
            self.close()

    def send_game_move(self, move_data):
        """发送游戏相关的移动"""
        try:
            self.client_socket.send(json.dumps(move_data).encode())
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送游戏数据失败: {str(e)}")
            if self.game_window:
                self.game_window.close()

    def handle_game_move(self, data):
        """处理游戏相关的移动"""
        # 通过信号处理游戏动作
        self.signals.handle_game_action.emit(data)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    client = ChatClient()
    client.start()
    sys.exit(app.exec_()) 