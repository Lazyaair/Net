import socket
import threading
import json
import os
from datetime import datetime
import struct
import pickle
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QListWidget, 
                            QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QFont

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
    color: #67c23a;
}

QPushButton {
    background-color: #67c23a;
    color: white;
    border: none;
    padding: 5px 15px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #85ce61;
}

QPushButton:pressed {
    background-color: #5daf34;
}

QTextEdit {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 8px;
    font-size: 13px;
    background-color: white;
    font-family: "Consolas", monospace;
}

QListWidget {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 5px;
    font-size: 13px;
    background-color: white;
}

QListWidget::item {
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #f0f9eb;
    color: #67c23a;
}

QListWidget::item:hover {
    background-color: #f5f7fa;
}

QPushButton#kick_button {
    background-color: #f56c6c;
}

QPushButton#kick_button:hover {
    background-color: #f78989;
}

QPushButton#kick_button:pressed {
    background-color: #dd6161;
}

QPushButton#delete_button {
    background-color: #e6a23c;
}

QPushButton#delete_button:hover {
    background-color: #ebb563;
}

QPushButton#delete_button:pressed {
    background-color: #cf9236;
}
"""

class SignalManager(QObject):
    """信号管理器，用于线程间通信"""
    log_message = pyqtSignal(str)
    update_online_users = pyqtSignal(list)
    update_files = pyqtSignal(list)

class ChatServer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.host = 'localhost'
        self.port = 5000
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.clients = {}  # {client_socket: username}
        self.file_transfers = {}  # 用于跟踪文件传输状态
        self.emoji_transfers = {}  # 用于跟踪表情传输状态
        
        # 创建服务器文件存储目录
        if not os.path.exists('server_files'):
            os.makedirs('server_files')
            
        # 初始化服务器文件列表
        self.server_files = []
        
        # 创建信号管理器
        self.signals = SignalManager()
        self.signals.log_message.connect(self.append_log)
        self.signals.update_online_users.connect(self.update_online_users_gui)
        self.signals.update_files.connect(self.update_files_gui)
        
        # 设置GUI
        self.setup_gui()
        self.setStyleSheet(STYLE_SHEET)
        
        # 扫描文件
        self.scan_server_files()
        
        # 更新GUI显示
        self.update_file_list()
        
    def setup_gui(self):
        self.setWindowTitle("聊天服务器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建主窗口部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建左侧面板（在线用户）
        users_group = QGroupBox("在线用户")
        users_layout = QVBoxLayout()
        users_layout.setSpacing(10)
        
        self.online_list = QListWidget()
        self.kick_button = QPushButton("踢出选中用户")
        self.kick_button.setObjectName("kick_button")
        self.kick_button.setIcon(QIcon("emojis/icons8-疯-80.png"))
        self.kick_button.clicked.connect(self.kick_user)
        
        users_layout.addWidget(self.online_list)
        users_layout.addWidget(self.kick_button)
        users_group.setLayout(users_layout)
        
        # 创建中间面板（服务器文件）
        files_group = QGroupBox("服务器文件")
        files_layout = QVBoxLayout()
        files_layout.setSpacing(10)
        
        self.files_list = QListWidget()
        self.delete_button = QPushButton("删除选中文件")
        self.delete_button.setObjectName("delete_button")
        self.delete_button.setIcon(QIcon("emojis/icons8-剑-80.png"))
        self.delete_button.clicked.connect(self.delete_file)
        
        files_layout.addWidget(self.files_list)
        files_layout.addWidget(self.delete_button)
        files_group.setLayout(files_layout)
        
        # 创建右侧面板（日志）
        log_group = QGroupBox("服务器日志")
        log_layout = QVBoxLayout()
        log_layout.setSpacing(10)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        
        # 添加所有面板到主布局
        layout.addWidget(users_group)
        layout.addWidget(files_group)
        layout.addWidget(log_group)
        
        # 设置布局比例
        layout.setStretch(0, 1)  # 用户列表
        layout.setStretch(1, 1)  # 文件列表
        layout.setStretch(2, 2)  # 日志区域
        
    def log_message(self, message):
        """发送日志消息到GUI线程"""
        self.signals.log_message.emit(message)
        
    def append_log(self, message):
        """在GUI线程中添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"<span style='color: #858585;'>[{timestamp}]</span> <span style='color: #d4d4d4;'>{message}</span><br>"
        self.log_area.insertHtml(formatted_message)
        
    def update_online_users_gui(self, users):
        """在GUI线程中更新在线用户列表"""
        self.online_list.clear()
        self.online_list.addItems(users)
        
    def update_files_gui(self, files):
        """在GUI线程中更新文件列表"""
        self.files_list.clear()
        self.files_list.addItems(files)
        
    def scan_server_files(self):
        """扫描服务器文件目录"""
        try:
            self.server_files = os.listdir('server_files')
            self.log_message(f"扫描到 {len(self.server_files)} 个文件")
            self.signals.update_files.emit(self.server_files)
        except Exception as e:
            self.log_message(f"扫描文件目录失败: {str(e)}")
            self.server_files = []
            
    def broadcast(self, message, exclude_client=None):
        """发送服务器消息给所有客户端"""
        data = {
            'type': 'server_message',
            'content': message
        }
        for client in self.clients:
            if client != exclude_client:
                try:
                    client.send(json.dumps(data).encode())
                except:
                    self.remove_client(client)
                    
    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]
            del self.clients[client_socket]
            self.update_online_users()
            self.log_message(f"{username} 已断开连接")
            self.broadcast(f"SERVER: {username} 已离开聊天室")
            
    def update_online_users(self):
        """更新在线用户列表"""
        users_list = list(self.clients.values())
        self.signals.update_online_users.emit(users_list)
        
        # 向所有客户端发送更新后的用户列表
        data = json.dumps({
            'type': 'users_list',
            'users': users_list
        }).encode()
        
        for client in self.clients:
            try:
                client.send(data)
            except:
                self.remove_client(client)
                
    def update_file_list(self):
        """更新文件列表"""
        self.server_files = os.listdir('server_files')
        self.signals.update_files.emit(self.server_files)
        
        # 向所有客户端发送更新后的文件列表
        data = json.dumps({
            'type': 'files_list',
            'files': self.server_files
        }).encode()
        
        for client in self.clients:
            try:
                client.send(data)
                time.sleep(0.1)  # 添加短暂延时
            except:
                self.remove_client(client)

    def handle_client(self, client_socket, address):
        """处理客户端连接"""
        try:
            # 接收用户名
            username = client_socket.recv(1024).decode()
            if not username:
                return
                
            # 保存客户端信息
            self.clients[client_socket] = username
            self.log_message(f"{username} 已连接")
            
            # 先发送当前在线用户列表
            users_list = list(self.clients.values())
            users_data = json.dumps({
                'type': 'users_list',
                'users': users_list
            }).encode()
            try:
                client_socket.send(users_data)
                time.sleep(0.2)  # 增加延时
            except:
                self.remove_client(client_socket)
                return
            
            # 广播新用户加入
            self.broadcast(f"SERVER: {username} 加入了聊天室")
            time.sleep(0.2)  # 增加延时
            
            # 更新所有客户端的在线用户列表
            self.update_online_users()
            time.sleep(0.2)  # 增加延时
            
            # 发送当前服务器文件列表
            self.update_file_list()
            
            while True:
                try:
                    type_flag = client_socket.recv(1)
                    if not type_flag:
                        break
                        
                    if type_flag == b'\x01':  # 表情消息
                        length_data = client_socket.recv(4)
                        if not length_data:
                            break
                        msg_length = struct.unpack('>I', length_data)[0]
                        
                        data = b''
                        while len(data) < msg_length:
                            chunk = client_socket.recv(min(msg_length - len(data), 8192))
                            if not chunk:
                                break
                            data += chunk
                            
                        if len(data) == msg_length:
                            emoji_data = pickle.loads(data)
                            to = emoji_data.get('to', '所有人')
                            emoji_data['from'] = username
                            
                            if to == '所有人':
                                # 广播表情
                                for c in self.clients:
                                    if c != client_socket:
                                        try:
                                            c.send(b'\x01')
                                            c.send(struct.pack('>I', len(data)))
                                            c.send(data)
                                        except:
                                            self.remove_client(c)
                            else:
                                # 私发表情
                                for c, name in self.clients.items():
                                    if name == to:
                                        try:
                                            c.send(b'\x01')
                                            c.send(struct.pack('>I', len(data)))
                                            c.send(data)
                                        except:
                                            self.remove_client(c)
                                        break
                                        
                    elif type_flag == b'\x02':  # 文件消息
                        length_data = client_socket.recv(4)
                        if not length_data:
                            break
                        msg_length = struct.unpack('>I', length_data)[0]
                        
                        data = b''
                        while len(data) < msg_length:
                            chunk = client_socket.recv(min(msg_length - len(data), 8192))
                            if not chunk:
                                break
                            data += chunk
                            
                        if len(data) == msg_length:
                            file_data = pickle.loads(data)
                            
                            if file_data.get('action') == 'download':
                                # 处理下载请求
                                filename = file_data['filename']
                                save_path = file_data.get('save_path', filename)  # 获取客户端指定的保存路径
                                file_path = os.path.join('server_files', filename)
                                
                                if os.path.exists(file_path):
                                    with open(file_path, 'rb') as f:
                                        content = f.read()
                                    response = {
                                        'type': 'file',
                                        'filename': filename,
                                        'content': content,
                                        'save_path': save_path  # 将保存路径包含在响应中
                                    }
                                    data = pickle.dumps(response)
                                    try:
                                        client_socket.send(b'\x02')
                                        client_socket.send(struct.pack('>I', len(data)))
                                        client_socket.send(data)
                                        self.log_message(f"{username} 下载了文件: {filename}")
                                    except:
                                        self.remove_client(client_socket)
                                else:
                                    self.log_message(f"文件不存在: {filename}")
                            else:
                                # 处理上传请求
                                to = file_data.get('to', '所有人')
                                filename = file_data['filename']
                                content = file_data['content']
                                
                                if to == '所有人':
                                    # 保存到服务器
                                    file_path = os.path.join('server_files', filename)
                                    with open(file_path, 'wb') as f:
                                        f.write(content)
                                    self.log_message(f"{username} 上传了文件: {filename}")
                                    self.update_file_list()
                                else:
                                    # 私发文件
                                    file_data['from'] = username
                                    data = pickle.dumps(file_data)
                                    for c, name in self.clients.items():
                                        if name == to:
                                            try:
                                                c.send(b'\x02')
                                                c.send(struct.pack('>I', len(data)))
                                                c.send(data)
                                            except:
                                                self.remove_client(c)
                                            break
                                            
                    else:  # 普通消息
                        message = client_socket.recv(8191)
                        if not message:
                            break
                            
                        try:
                            data = json.loads((type_flag + message).decode())
                            if data['type'] == 'message':
                                to = data.get('to', '所有人')
                                content = data['content']
                                
                                if to == '所有人':
                                    # 广播消息
                                    broadcast_data = {
                                        'type': 'message',
                                        'from': username,
                                        'content': content
                                    }
                                    for c in self.clients:
                                        if c != client_socket:
                                            try:
                                                c.send(json.dumps(broadcast_data).encode())
                                            except:
                                                self.remove_client(c)
                                else:
                                    # 私聊消息
                                    private_data = {
                                        'type': 'private_message',
                                        'from': username,
                                        'content': content
                                    }
                                    for c, name in self.clients.items():
                                        if name == to:
                                            try:
                                                c.send(json.dumps(private_data).encode())
                                            except:
                                                self.remove_client(c)
                                            break
                                            
                            elif data['type'] == 'game_invite':
                                # 处理游戏邀请
                                to = data['to']
                                invite_data = {
                                    'type': 'game_invite',
                                    'from': username,
                                    'to': to
                                }
                                # 转发邀请给目标用户
                                for c, name in self.clients.items():
                                    if name == to:
                                        try:
                                            c.send(json.dumps(invite_data).encode())
                                            self.log_message(f"{username} 向 {to} 发送了游戏邀请")
                                        except:
                                            self.remove_client(c)
                                        break
                                            
                            elif data['type'] == 'game_invite_response':
                                # 处理游戏邀请响应
                                to = data['to']
                                response_data = {
                                    'type': 'game_invite_response',
                                    'from': username,
                                    'to': to,
                                    'accepted': data['accepted']
                                }
                                # 转发响应给发起邀请的用户
                                for c, name in self.clients.items():
                                    if name == to:
                                        try:
                                            c.send(json.dumps(response_data).encode())
                                            self.log_message(
                                                f"{username} {'接受' if data['accepted'] else '拒绝'}了 {to} 的游戏邀请"
                                            )
                                        except:
                                            self.remove_client(c)
                                        break
                                            
                            elif data['type'] == 'game_move':
                                # 处理游戏相关的移动
                                to = data['to']
                                move_data = data.copy()
                                move_data['from'] = username
                                
                                # 转发游戏数据给对手
                                for c, name in self.clients.items():
                                    if name == to:
                                        try:
                                            c.send(json.dumps(move_data).encode())
                                            action = data.get('action', '')
                                            if action == 'move':
                                                self.log_message(f"游戏移动: {username} -> {to}")
                                            elif action == 'win':
                                                self.log_message(f"游戏结束: {username} 获胜")
                                            elif action == 'surrender':
                                                self.log_message(f"游戏结束: {username} 认输")
                                            elif action == 'draw_request':
                                                self.log_message(f"{username} 向 {to} 请求和棋")
                                            elif action == 'draw_response':
                                                self.log_message(
                                                    f"{username} {'接受' if data['accepted'] else '拒绝'}了 {to} 的和棋请求"
                                                )
                                        except:
                                            self.remove_client(c)
                                        break
                                            
                        except json.JSONDecodeError:
                            self.log_message(f"JSON解析错误: {(type_flag + message).decode()}")
                            
                except Exception as e:
                    self.log_message(f"处理客户端消息时出错: {str(e)}")
                    break
                    
        except Exception as e:
            self.log_message(f"处理客户端连接时出错: {str(e)}")
            
        finally:
            self.remove_client(client_socket)
            
    def start(self):
        self.log_message("服务器已启动...")
        
        # 启动接受客户端连接的线程
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()
        
        # 显示窗口
        self.show()

    def accept_connections(self):
        while True:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                self.log_message(f"接受连接时出错: {str(e)}")
                break
                
    def kick_user(self):
        """踢出选中的用户"""
        current_item = self.online_list.currentItem()
        if not current_item:
            return
            
        username = current_item.text()
        for client_socket, name in self.clients.items():
            if name == username:
                try:
                    # 发送踢出消息
                    kick_msg = {
                        'type': 'server_message',
                        'content': '您已被服务器强制下线'
                    }
                    client_socket.send(json.dumps(kick_msg).encode())
                    # 关闭连接
                    client_socket.close()
                    # 从客户端列表中移除
                    self.remove_client(client_socket)
                    self.log_message(f"已强制用户 {username} 下线")
                except:
                    self.log_message(f"踢出用户 {username} 失败")
                break
                
    def delete_file(self):
        """删除选中的文件"""
        current_item = self.files_list.currentItem()
        if not current_item:
            return
            
        filename = current_item.text()
        file_path = os.path.join('server_files', filename)
        try:
            os.remove(file_path)
            self.log_message(f"已删除文件: {filename}")
            self.update_file_list()
        except Exception as e:
            self.log_message(f"删除文件失败: {str(e)}")

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    server = ChatServer()
    server.start()
    sys.exit(app.exec_()) 