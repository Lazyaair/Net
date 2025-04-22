package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"
)

type Client struct {
	conn     net.Conn
	username string
}

type Server struct {
	clients      map[net.Conn]*Client
	clientsMux   sync.RWMutex
	window       fyne.Window
	logArea      *widget.Entry
	usersList    *widget.List
	filesList    *widget.List
	users        []string
	files        []string
	selectedUser int
	selectedFile int
}

func NewServer() *Server {
	// 创建服务器文件目录
	if err := os.MkdirAll("server_files", 0755); err != nil {
		log.Fatal(err)
	}

	return &Server{
		clients:      make(map[net.Conn]*Client),
		users:        make([]string, 0),
		files:        make([]string, 0),
		selectedUser: -1,
		selectedFile: -1,
	}
}

func (s *Server) setupGUI() {
	myApp := app.New()
	s.window = myApp.NewWindow("聊天服务器")

	// 创建日志区域
	s.logArea = widget.NewMultiLineEntry()
	s.logArea.SetText("服务器已启动...\n")
	s.logArea.Disable()

	// 创建用户列表
	s.usersList = widget.NewList(
		func() int { return len(s.users) },
		func() fyne.CanvasObject { return widget.NewLabel("") },
		func(id widget.ListItemID, obj fyne.CanvasObject) {
			obj.(*widget.Label).SetText(s.users[id])
		},
	)
	s.usersList.OnSelected = func(id widget.ListItemID) {
		s.selectedUser = int(id)
	}

	// 创建文件列表
	s.filesList = widget.NewList(
		func() int { return len(s.files) },
		func() fyne.CanvasObject { return widget.NewLabel("") },
		func(id widget.ListItemID, obj fyne.CanvasObject) {
			obj.(*widget.Label).SetText(s.files[id])
		},
	)
	s.filesList.OnSelected = func(id widget.ListItemID) {
		s.selectedFile = int(id)
	}

	// 更新文件列表
	s.updateFilesList()

	// 创建踢出用户按钮
	kickButton := widget.NewButton("踢出选中用户", s.kickSelectedUser)

	// 创建删除文件按钮
	deleteButton := widget.NewButton("删除选中文件", s.deleteSelectedFile)

	// 创建布局
	usersBox := container.NewBorder(nil, kickButton, nil, nil, s.usersList)
	filesBox := container.NewBorder(nil, deleteButton, nil, nil, s.filesList)
	rightSide := container.NewVSplit(
		container.NewBorder(widget.NewLabel("在线用户"), nil, nil, nil, usersBox),
		container.NewBorder(widget.NewLabel("服务器文件"), nil, nil, nil, filesBox),
	)
	content := container.NewHSplit(
		container.NewBorder(widget.NewLabel("服务器日志"), nil, nil, nil, s.logArea),
		rightSide,
	)

	s.window.SetContent(content)
	s.window.Resize(fyne.NewSize(800, 600))
}

func (s *Server) log(message string) {
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	logMessage := fmt.Sprintf("[%s] %s\n", timestamp, message)
	currentText := s.logArea.Text
	s.logArea.SetText(currentText + logMessage)
}

func (s *Server) updateUsersList() {
	s.clientsMux.RLock()
	s.users = make([]string, 0, len(s.clients))
	for _, client := range s.clients {
		s.users = append(s.users, client.username)
	}
	s.clientsMux.RUnlock()
	s.usersList.Refresh()

	// 向所有客户端发送更新后的用户列表
	data := map[string]interface{}{
		"type":  "users_list",
		"users": s.users,
	}
	s.broadcast(data)
}

func (s *Server) updateFilesList() {
	// 确保server_files目录存在
	if err := os.MkdirAll("server_files", 0755); err != nil {
		s.log(fmt.Sprintf("创建文件目录失败: %v", err))
		return
	}

	files, err := os.ReadDir("server_files")
	if err != nil {
		s.log(fmt.Sprintf("读取文件目录失败: %v", err))
		return
	}

	s.files = make([]string, 0)
	for _, file := range files {
		if !file.IsDir() {
			s.files = append(s.files, file.Name())
		}
	}

	// 添加日志以便调试
	s.log(fmt.Sprintf("更新文件列表: 找到 %d 个文件", len(s.files)))
	for _, file := range s.files {
		s.log(fmt.Sprintf("文件: %s", file))
	}

	s.filesList.Refresh()

	// 向所有客户端发送更新后的文件列表
	data := map[string]interface{}{
		"type":  "files_list",
		"files": s.files,
	}
	s.broadcast(data)
}

func (s *Server) broadcast(data interface{}) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		s.log(fmt.Sprintf("广播消息序列化失败: %v", err))
		return
	}

	s.clientsMux.RLock()
	defer s.clientsMux.RUnlock()

	for conn := range s.clients {
		err := s.sendMessage(conn, jsonData)
		if err != nil {
			s.log(fmt.Sprintf("发送消息失败: %v", err))
			s.removeClient(conn)
		}
	}
}

func (s *Server) sendMessage(conn net.Conn, data []byte) error {
	_, err := conn.Write(append([]byte{0}, data...)) // 0表示普通消息
	return err
}

func (s *Server) removeClient(conn net.Conn) {
	s.clientsMux.Lock()
	if client, ok := s.clients[conn]; ok {
		s.log(fmt.Sprintf("%s 已断开连接", client.username))
		delete(s.clients, conn)
		conn.Close()
	}
	s.clientsMux.Unlock()
	s.updateUsersList()
}

func (s *Server) kickSelectedUser() {
	if s.selectedUser < 0 || s.selectedUser >= len(s.users) {
		return
	}

	username := s.users[s.selectedUser]
	s.clientsMux.RLock()
	for conn, client := range s.clients {
		if client.username == username {
			// 发送踢出消息
			kickMsg := map[string]interface{}{
				"type":    "server_message",
				"content": "您已被服务器强制下线",
			}
			jsonData, _ := json.Marshal(kickMsg)
			s.sendMessage(conn, jsonData)
			s.removeClient(conn)
			s.log(fmt.Sprintf("已强制用户 %s 下线", username))
			break
		}
	}
	s.clientsMux.RUnlock()
}

func (s *Server) deleteSelectedFile() {
	if s.selectedFile < 0 || s.selectedFile >= len(s.files) {
		return
	}

	filename := s.files[s.selectedFile]
	err := os.Remove(filepath.Join("server_files", filename))
	if err != nil {
		s.log(fmt.Sprintf("删除文件失败: %v", err))
		return
	}

	s.log(fmt.Sprintf("已删除文件: %s", filename))
	s.updateFilesList()
}

func (s *Server) handleClient(conn net.Conn) {
	defer s.removeClient(conn)

	// 接收用户名
	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		return
	}
	username := string(buffer[:n])

	// 保存客户端信息
	s.clientsMux.Lock()
	s.clients[conn] = &Client{conn: conn, username: username}
	s.clientsMux.Unlock()

	s.log(fmt.Sprintf("%s 已连接", username))

	// 发送当前在线用户列表
	s.updateUsersList()

	// 发送当前文件列表
	s.updateFilesList()

	// 广播新用户加入
	s.broadcast(map[string]interface{}{
		"type":    "server_message",
		"content": fmt.Sprintf("SERVER: %s 加入了聊天室", username),
	})

	for {
		// 读取消息类型
		typeBuffer := make([]byte, 1)
		_, err := conn.Read(typeBuffer)
		if err != nil {
			break
		}

		switch typeBuffer[0] {
		case 0: // 普通消息
			buffer := make([]byte, 8192)
			n, err := conn.Read(buffer)
			if err != nil {
				return
			}

			var data map[string]interface{}
			if err := json.Unmarshal(buffer[:n], &data); err != nil {
				s.log(fmt.Sprintf("JSON解析错误: %v", err))
				continue
			}

			if data["type"] == "message" {
				to := data["to"].(string)
				content := data["content"].(string)

				if to == "所有人" {
					// 广播消息
					broadcastData := map[string]interface{}{
						"type":    "message",
						"from":    username,
						"content": content,
					}
					s.broadcast(broadcastData)
				} else {
					// 私聊消息
					privateData := map[string]interface{}{
						"type":    "private_message",
						"from":    username,
						"content": content,
					}
					s.sendPrivateMessage(to, privateData)
				}
			}

		case 1: // 表情消息
			// 读取数据长度
			lenBuffer := make([]byte, 4)
			_, err := io.ReadFull(conn, lenBuffer)
			if err != nil {
				return
			}
			dataLen := binary.BigEndian.Uint32(lenBuffer)

			// 读取数据
			data := make([]byte, dataLen)
			_, err = io.ReadFull(conn, data)
			if err != nil {
				return
			}

			// 转发表情
			s.clientsMux.RLock()
			for c := range s.clients {
				if c != conn {
					c.Write([]byte{1})
					c.Write(lenBuffer)
					c.Write(data)
				}
			}
			s.clientsMux.RUnlock()

		case 2: // 文件消息
			// 读取数据长度
			lenBuffer := make([]byte, 4)
			_, err := io.ReadFull(conn, lenBuffer)
			if err != nil {
				return
			}
			dataLen := binary.BigEndian.Uint32(lenBuffer)

			// 读取数据
			data := make([]byte, dataLen)
			_, err = io.ReadFull(conn, data)
			if err != nil {
				return
			}

			var fileData map[string]interface{}
			if err := json.Unmarshal(data, &fileData); err != nil {
				s.log(fmt.Sprintf("文件数据解析错误: %v", err))
				continue
			}

			if action, ok := fileData["action"].(string); ok && action == "download" {
				// 处理下载请求
				filename := fileData["filename"].(string)
				filePath := filepath.Join("server_files", filename)
				fileContent, err := os.ReadFile(filePath)
				if err != nil {
					s.log(fmt.Sprintf("读取文件失败: %v", err))
					continue
				}

				response := map[string]interface{}{
					"type":     "file",
					"filename": filename,
					"content":  fileContent,
				}
				responseData, _ := json.Marshal(response)
				conn.Write([]byte{2})
				binary.Write(conn, binary.BigEndian, uint32(len(responseData)))
				conn.Write(responseData)
			} else {
				// 处理上传请求
				filename := fileData["filename"].(string)
				content := fileData["content"].([]byte)
				filePath := filepath.Join("server_files", filename)

				err := os.WriteFile(filePath, content, 0644)
				if err != nil {
					s.log(fmt.Sprintf("保存文件失败: %v", err))
					continue
				}

				s.log(fmt.Sprintf("%s 上传了文件: %s", username, filename))
				s.updateFilesList()
			}
		}
	}
}

func (s *Server) sendPrivateMessage(to string, data interface{}) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		s.log(fmt.Sprintf("私聊消息序列化失败: %v", err))
		return
	}

	s.clientsMux.RLock()
	defer s.clientsMux.RUnlock()

	for _, client := range s.clients {
		if client.username == to {
			err := s.sendMessage(client.conn, jsonData)
			if err != nil {
				s.log(fmt.Sprintf("发送私聊消息失败: %v", err))
				s.removeClient(client.conn)
			}
			break
		}
	}
}

func (s *Server) start() {
	listener, err := net.Listen("tcp", ":5000")
	if err != nil {
		log.Fatal(err)
	}
	defer listener.Close()

	s.log("服务器已启动，监听端口 5000")

	for {
		conn, err := listener.Accept()
		if err != nil {
			s.log(fmt.Sprintf("接受连接失败: %v", err))
			continue
		}

		go s.handleClient(conn)
	}
}

func main() {
	server := NewServer()
	server.setupGUI()

	// 确保GUI完全设置后再启动服务
	go func() {
		time.Sleep(time.Second) // 等待GUI完全初始化
		server.start()
	}()

	server.window.ShowAndRun()
}
