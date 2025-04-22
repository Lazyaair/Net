from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QMessageBox)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

# 添加游戏窗口样式表
GAME_STYLE_SHEET = """
QWidget {
    background-color: #f0f2f5;
}

QLabel {
    color: #303133;
    font-size: 14px;
    padding: 5px;
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

QPushButton#surrender_button {
    background-color: #f56c6c;
}

QPushButton#surrender_button:hover {
    background-color: #f78989;
}

QPushButton#draw_button {
    background-color: #e6a23c;
}

QPushButton#draw_button:hover {
    background-color: #ebb563;
}
"""

class WuziBoard(QWidget):
    # 定义信号
    move_made = pyqtSignal(int, int)  # 发出下棋位置的信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board_size = 15  # 15x15的棋盘
        self.grid_size = 30   # 每个格子的大小
        self.piece_size = 28  # 棋子的大小
        self.board = [[0] * self.board_size for _ in range(self.board_size)]  # 0表示空，1表示黑子，2表示白子
        self.is_black_turn = True  # True表示该黑子下，False表示该白子下
        self.is_my_turn = False    # 是否轮到自己下棋
        self.is_game_over = False  # 游戏是否结束
        
        # 设置固定大小
        board_width = (self.board_size + 1) * self.grid_size
        self.setFixedSize(board_width, board_width)
        self.setStyleSheet("background-color: #FFCC99;")
        
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制网格线
            pen = QPen(Qt.black, 1, Qt.SolidLine)
            painter.setPen(pen)
            
            # 绘制横线和竖线
            for i in range(self.board_size):
                # 横线
                painter.drawLine(self.grid_size, (i + 1) * self.grid_size,
                               self.board_size * self.grid_size, (i + 1) * self.grid_size)
                # 竖线
                painter.drawLine((i + 1) * self.grid_size, self.grid_size,
                               (i + 1) * self.grid_size, self.board_size * self.grid_size)
            
            # 绘制棋子
            for i in range(self.board_size):
                for j in range(self.board_size):
                    if self.board[i][j] != 0:
                        if self.board[i][j] == 1:  # 黑子
                            painter.setBrush(QBrush(Qt.black))
                        else:  # 白子
                            painter.setBrush(QBrush(Qt.white))
                        
                        center_x = (j + 1) * self.grid_size
                        center_y = (i + 1) * self.grid_size
                        painter.drawEllipse(center_x - self.piece_size//2,
                                          center_y - self.piece_size//2,
                                          self.piece_size,
                                          self.piece_size)
        except Exception as e:
            print(f"绘制棋盘错误: {str(e)}")
    
    def mousePressEvent(self, event):
        if not self.is_my_turn or self.is_game_over:
            return
            
        # 获取点击的位置
        x = event.x()
        y = event.y()
        
        # 转换为棋盘坐标
        board_x = round((x - self.grid_size) / self.grid_size)
        board_y = round((y - self.grid_size) / self.grid_size)
        
        # 检查是否在有效范围内
        if 0 <= board_x < self.board_size and 0 <= board_y < self.board_size:
            # 检查该位置是否已经有棋子
            if self.board[board_y][board_x] == 0:
                # 发出移动信号
                self.move_made.emit(board_x, board_y)
    
    def make_move(self, x, y, is_black):
        """在指定位置放置棋子"""
        if 0 <= x < self.board_size and 0 <= y < self.board_size:
            self.board[y][x] = 1 if is_black else 2
            self.update()  # 重绘棋盘
            return self.check_win(x, y)
        return False
    
    def check_win(self, x, y):
        """检查是否获胜"""
        directions = [(1,0), (0,1), (1,1), (1,-1)]  # 横向、纵向、主对角线、副对角线
        piece = self.board[y][x]
        
        for dx, dy in directions:
            count = 1  # 当前方向的连续相同棋子数
            
            # 正向检查
            temp_x, temp_y = x + dx, y + dy
            while 0 <= temp_x < self.board_size and 0 <= temp_y < self.board_size and self.board[temp_y][temp_x] == piece:
                count += 1
                temp_x += dx
                temp_y += dy
            
            # 反向检查
            temp_x, temp_y = x - dx, y - dy
            while 0 <= temp_x < self.board_size and 0 <= temp_y < self.board_size and self.board[temp_y][temp_x] == piece:
                count += 1
                temp_x -= dx
                temp_y -= dy
            
            if count >= 5:
                return True
        return False
    
    def reset_game(self):
        """重置游戏"""
        self.board = [[0] * self.board_size for _ in range(self.board_size)]
        self.is_black_turn = True
        self.is_game_over = False
        self.update()

class WuziWindow(QWidget):
    game_move = pyqtSignal(dict)  # 发送游戏相关的信号
    
    def __init__(self, username, opponent, is_black, parent=None):
        try:
            super().__init__(parent)
            self.username = username
            self.opponent = opponent
            self.is_black = is_black
            
            # 创建棋盘
            self.board = WuziBoard()
            self.board.is_my_turn = self.is_black  # 黑子先手
            
            # 设置窗口属性
            self.setWindowTitle(f"五子棋 - 对战 {self.opponent}")
            self.setFixedSize(600, 550)
            self.setStyleSheet(GAME_STYLE_SHEET)
            
            # 设置界面
            self.setup_ui()
        except Exception as e:
            print(f"初始化游戏窗口错误: {str(e)}")
            QMessageBox.critical(None, "错误", f"创建游戏窗口失败: {str(e)}")
        
    def setup_ui(self):
        try:
            layout = QVBoxLayout()
            layout.setSpacing(10)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # 状态标签
            self.status_label = QLabel()
            self.status_label.setAlignment(Qt.AlignCenter)
            self.update_status_label()
            layout.addWidget(self.status_label)
            
            # 连接棋盘信号
            self.board.move_made.connect(self.on_move_made)
            layout.addWidget(self.board)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            button_layout.setSpacing(10)
            
            self.surrender_button = QPushButton("认输")
            self.surrender_button.setObjectName("surrender_button")
            self.surrender_button.clicked.connect(self.on_surrender)
            
            self.draw_button = QPushButton("求和")
            self.draw_button.setObjectName("draw_button")
            self.draw_button.clicked.connect(self.on_draw_request)
            
            button_layout.addWidget(self.surrender_button)
            button_layout.addWidget(self.draw_button)
            layout.addLayout(button_layout)
            
            self.setLayout(layout)
        except Exception as e:
            print(f"设置游戏界面错误: {str(e)}")
            raise  # 重新抛出异常，这样可以在外层捕获
            
    def update_status_label(self):
        if self.board.is_game_over:
            self.status_label.setText("游戏结束")
        else:
            turn_text = "黑方" if self.board.is_black_turn else "白方"
            my_turn_text = "轮到你下棋" if self.board.is_my_turn else "等待对方下棋"
            self.status_label.setText(f"当前回合: {turn_text} - {my_turn_text}")
    
    def on_move_made(self, x, y):
        """处理下棋事件"""
        # 先发送移动消息
        move_data = {
            'type': 'game_move',
            'action': 'move',
            'x': x,
            'y': y,
            'to': self.opponent
        }
        self.game_move.emit(move_data)
        
        # 更新棋盘
        if self.board.make_move(x, y, self.is_black):
            # 等待一小段时间，确保对方收到移动消息并更新棋盘
            QTimer.singleShot(100, lambda: self.declare_victory())
        else:
            # 切换回合
            self.board.is_my_turn = False
            self.board.is_black_turn = not self.board.is_black_turn
            self.update_status_label()
    
    def declare_victory(self):
        """宣布获胜"""
        # 发送获胜消息
        move_data = {
            'type': 'game_move',
            'action': 'win',
            'to': self.opponent
        }
        self.game_move.emit(move_data)
        QMessageBox.information(self, "游戏结束", "恭喜你获胜！")
        self.board.is_game_over = True
        self.update_status_label()
    
    def on_opponent_move(self, x, y):
        """处理对手的下棋"""
        if self.board.make_move(x, y, not self.is_black):
            # 对手获胜
            QMessageBox.information(self, "游戏结束", "你输了！")
            self.board.is_game_over = True
            self.update_status_label()
        else:
            # 切换回合
            self.board.is_my_turn = True
            self.board.is_black_turn = not self.board.is_black_turn
            self.update_status_label()
    
    def on_surrender(self):
        """处理认输"""
        reply = QMessageBox.question(self, "确认认输", 
                                   "确定要认输吗？", 
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            move_data = {
                'type': 'game_move',
                'action': 'surrender',
                'to': self.opponent
            }
            self.game_move.emit(move_data)
            QMessageBox.information(self, "游戏结束", "你已认输！")
            self.board.is_game_over = True
            self.update_status_label()
    
    def on_draw_request(self):
        """处理求和请求"""
        reply = QMessageBox.question(self, "确认求和", 
                                   "确定要向对手请求和棋吗？", 
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            move_data = {
                'type': 'game_move',
                'action': 'draw_request',
                'to': self.opponent
            }
            self.game_move.emit(move_data)
    
    def handle_draw_response(self, accepted):
        """处理对手对求和的回应"""
        if accepted:
            QMessageBox.information(self, "游戏结束", "双方同意和棋！")
            self.board.is_game_over = True
            self.update_status_label()
        else:
            QMessageBox.information(self, "求和被拒绝", "对手拒绝了和棋请求。")
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            if hasattr(self, 'board') and not self.board.is_game_over:
                reply = QMessageBox.question(self, "确认退出", 
                                           "游戏正在进行中，确定要退出吗？退出将视为认输。", 
                                           QMessageBox.Yes | QMessageBox.No)
                
                if reply == QMessageBox.Yes:
                    move_data = {
                        'type': 'game_move',
                        'action': 'surrender',
                        'to': self.opponent
                    }
                    self.game_move.emit(move_data)
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        except Exception as e:
            print(f"关闭窗口错误: {str(e)}")
            event.accept()  # 如果出现错误，也接受关闭事件 