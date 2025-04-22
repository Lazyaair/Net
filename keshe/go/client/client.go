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

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

type Client struct {
	conn         net.Conn
	username     string
	window       fyne.Window
	chatArea     *widget.TextGrid
	usersList    *widget.List
	filesList    *widget.List
	msgInput     *widget.Entry
	users        []string
	files        []string
	selectedUser int
	selectedFile int
	buttons      *ClientButtons
	enabled      bool
}

type ClientButtons struct {
	sendButton     *widget.Button
	fileButton     *widget.Button
	emojiButton    *widget.Button
	downloadButton *widget.Button
}

func NewClient() *Client {
	return &Client{
		users:        make([]string, 0),
		files:        make([]string, 0),
		selectedUser: -1,
		selectedFile: -1,
	}
}

func (c *Client) setupGUI(myApp fyne.App) {
	c.window = myApp.NewWindow("聊天客户端")

	// 创建聊天区域
	c.chatArea = widget.NewTextGrid()
	c.chatArea.SetText("")

	// 创建消息输入框
	c.msgInput = widget.NewMultiLineEntry()
	c.msgInput.SetPlaceHolder("输入消息...")
	c.msgInput.Disable()

	// 创建发送按钮
	sendButton := widget.NewButton("发送", c.sendMessage)
	fileButton := widget.NewButton("发送文件", c.sendFile)
	emojiButton := widget.NewButton("发送表情", c.showEmojiSelector)

	// 初始禁用所有按钮
	sendButton.Disable()
	fileButton.Disable()
	emojiButton.Disable()

	// 创建用户列表
	c.usersList = widget.NewList(
		func() int { return len(c.users) },
		func() fyne.CanvasObject { return widget.NewLabel("") },
		func(id widget.ListItemID, obj fyne.CanvasObject) {
			obj.(*widget.Label).SetText(c.users[id])
		},
	)
	c.usersList.OnSelected = func(id widget.ListItemID) {
		if !c.enabled {
			return
		}
		c.selectedUser = int(id)
	}

	// 创建文件列表
	c.filesList = widget.NewList(
		func() int { return len(c.files) },
		func() fyne.CanvasObject { return widget.NewLabel("") },
		func(id widget.ListItemID, obj fyne.CanvasObject) {
			obj.(*widget.Label).SetText(c.files[id])
		},
	)
	c.filesList.OnSelected = func(id widget.ListItemID) {
		if !c.enabled {
			return
		}
		c.selectedFile = int(id)
	}

	// 创建下载按钮
	downloadButton := widget.NewButton("下载选中文件", c.downloadFile)
	downloadButton.Disable()

	// 保存按钮引用以便后续启用
	c.buttons = &ClientButtons{
		sendButton:     sendButton,
		fileButton:     fileButton,
		emojiButton:    emojiButton,
		downloadButton: downloadButton,
	}

	// 创建布局
	buttons := container.NewHBox(sendButton, fileButton, emojiButton)
	inputArea := container.NewBorder(nil, nil, nil, buttons, c.msgInput)
	chatBox := container.NewBorder(nil, inputArea, nil, nil, c.chatArea)

	usersBox := container.NewBorder(widget.NewLabel("在线用户"), nil, nil, nil, c.usersList)
	filesBox := container.NewBorder(widget.NewLabel("服务器文件"), downloadButton, nil, nil, c.filesList)
	rightSide := container.NewVSplit(usersBox, filesBox)

	content := container.NewHSplit(chatBox, rightSide)
	c.window.SetContent(content)
	c.window.Resize(fyne.NewSize(800, 600))

	// 设置主窗口关闭时的处理
	c.window.SetOnClosed(func() {
		if c.conn != nil {
			c.conn.Close()
		}
		myApp.Quit()
	})
}

func (c *Client) appendMessage(message string) {
	currentText := c.chatArea.Text()
	newText := currentText + message + "\n"
	c.chatArea.SetText(newText)
}

func (c *Client) updateUsersList(users []string) {
	// 创建新的用户列表，第一个是"所有人"
	c.users = make([]string, 1, len(users)+1)
	c.users[0] = "所有人"

	// 添加其他用户，排除自己
	for _, user := range users {
		if user != c.username {
			c.users = append(c.users, user)
		}
	}

	// 如果当前选中的不是"所有人"且索引无效，重置为"所有人"
	if c.selectedUser != 0 && (c.selectedUser < 0 || c.selectedUser >= len(c.users)) {
		c.selectedUser = 0
	}

	c.usersList.Refresh()
}

func (c *Client) updateFilesList(files []string) {
	c.files = files
	c.filesList.Refresh()
}

func (c *Client) sendMessage() {
	message := c.msgInput.Text
	if message == "" {
		return
	}

	// 获取接收者，默认是"所有人"
	to := "所有人"
	if c.selectedUser > 0 && c.selectedUser < len(c.users) {
		to = c.users[c.selectedUser]
	}

	data := map[string]interface{}{
		"type":    "message",
		"content": message,
		"to":      to,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		dialog.ShowError(fmt.Errorf("消息序列化失败: %v", err), c.window)
		return
	}

	_, err = c.conn.Write(append([]byte{0}, jsonData...))
	if err != nil {
		dialog.ShowError(fmt.Errorf("发送消息失败: %v", err), c.window)
		return
	}

	if to == "所有人" {
		c.appendMessage(fmt.Sprintf("你: %s", message))
	} else {
		c.appendMessage(fmt.Sprintf("你对%s说: %s", to, message))
	}

	c.msgInput.SetText("")
}

func (c *Client) sendFile() {
	fd := dialog.NewFileOpen(func(reader fyne.URIReadCloser, err error) {
		if err != nil {
			dialog.ShowError(err, c.window)
			return
		}
		if reader == nil {
			return
		}
		defer reader.Close()

		data, err := io.ReadAll(reader)
		if err != nil {
			dialog.ShowError(fmt.Errorf("读取文件失败: %v", err), c.window)
			return
		}

		// 获取接收者，默认是"所有人"
		to := "所有人"
		if c.selectedUser > 0 && c.selectedUser < len(c.users) {
			to = c.users[c.selectedUser]
		}

		fileData := map[string]interface{}{
			"type":     "file",
			"filename": filepath.Base(reader.URI().Path()),
			"content":  data,
			"to":       to,
		}

		jsonData, err := json.Marshal(fileData)
		if err != nil {
			dialog.ShowError(fmt.Errorf("文件数据序列化失败: %v", err), c.window)
			return
		}

		// 发送文件数据
		c.conn.Write([]byte{2})
		binary.Write(c.conn, binary.BigEndian, uint32(len(jsonData)))
		c.conn.Write(jsonData)

		c.appendMessage(fmt.Sprintf("文件 %s 发送完成", filepath.Base(reader.URI().Path())))
	}, c.window)
	fd.Show()
}

func (c *Client) downloadFile() {
	if c.selectedFile < 0 || c.selectedFile >= len(c.files) {
		dialog.ShowInformation("提示", "请先选择要下载的文件", c.window)
		return
	}

	filename := c.files[c.selectedFile]
	fd := dialog.NewFileSave(func(writer fyne.URIWriteCloser, err error) {
		if err != nil {
			dialog.ShowError(err, c.window)
			return
		}
		if writer == nil {
			return
		}
		defer writer.Close()

		// 发送下载请求
		downloadData := map[string]interface{}{
			"type":     "file",
			"action":   "download",
			"filename": filename,
		}

		jsonData, err := json.Marshal(downloadData)
		if err != nil {
			dialog.ShowError(fmt.Errorf("下载请求序列化失败: %v", err), c.window)
			return
		}

		c.conn.Write([]byte{2})
		binary.Write(c.conn, binary.BigEndian, uint32(len(jsonData)))
		c.conn.Write(jsonData)

		c.appendMessage(fmt.Sprintf("文件 %s 下载完成", filename))
	}, c.window)
	fd.SetFileName(filename)
	fd.Show()
}

func (c *Client) showEmojiSelector() {
	// 创建表情选择窗口
	emojiWindow := app.New().NewWindow("选择表情")
	emojiWindow.Resize(fyne.NewSize(400, 300))

	// 创建表情网格
	grid := container.NewGridWithColumns(5)

	// 加载表情
	emojiDir := "emojis"
	if _, err := os.Stat(emojiDir); os.IsNotExist(err) {
		os.MkdirAll(emojiDir, 0755)
	}

	files, err := os.ReadDir(emojiDir)
	if err != nil {
		dialog.ShowError(fmt.Errorf("加载表情失败: %v", err), c.window)
		return
	}

	for _, file := range files {
		if filepath.Ext(file.Name()) == ".png" {
			filePath := filepath.Join(emojiDir, file.Name())
			img := canvas.NewImageFromFile(filePath)
			img.Resize(fyne.NewSize(40, 40))
			img.FillMode = canvas.ImageFillOriginal

			// 创建一个包含图片的容器
			emojiContainer := container.NewMax(img)
			grid.Add(container.NewHBox(
				emojiContainer,
				widget.NewButton("选择", func(path string) func() {
					return func() {
						c.sendEmoji(path)
						emojiWindow.Close()
					}
				}(filePath)),
			))
		}
	}

	emojiWindow.SetContent(grid)
	emojiWindow.Show()
}

func (c *Client) sendEmoji(path string) {
	data, err := os.ReadFile(path)
	if err != nil {
		dialog.ShowError(fmt.Errorf("读取表情文件失败: %v", err), c.window)
		return
	}

	to := "所有人"
	if c.selectedUser >= 0 && c.selectedUser < len(c.users) {
		to = c.users[c.selectedUser]
	}

	emojiData := map[string]interface{}{
		"type":  "emoji",
		"image": data,
		"to":    to,
	}

	jsonData, err := json.Marshal(emojiData)
	if err != nil {
		dialog.ShowError(fmt.Errorf("表情数据序列化失败: %v", err), c.window)
		return
	}

	c.conn.Write([]byte{1})
	binary.Write(c.conn, binary.BigEndian, uint32(len(jsonData)))
	c.conn.Write(jsonData)

	if to == "所有人" {
		c.appendMessage("你: [表情]")
	} else {
		c.appendMessage(fmt.Sprintf("你对%s说: [表情]", to))
	}
}

func (c *Client) receiveMessages() {
	for {
		typeBuffer := make([]byte, 1)
		_, err := c.conn.Read(typeBuffer)
		if err != nil {
			if err != io.EOF {
				log.Printf("读取消息类型失败: %v", err)
			}
			break
		}

		switch typeBuffer[0] {
		case 0: // 普通消息
			buffer := make([]byte, 8192)
			n, err := c.conn.Read(buffer)
			if err != nil {
				log.Printf("读取消息内容失败: %v", err)
				return
			}

			var data map[string]interface{}
			if err := json.Unmarshal(buffer[:n], &data); err != nil {
				log.Printf("JSON解析错误: %v", err)
				continue
			}

			switch data["type"] {
			case "private_message":
				c.appendMessage(fmt.Sprintf("%s对你说: %s", data["from"], data["content"]))
			case "users_list":
				if users, ok := data["users"].([]interface{}); ok {
					usersList := make([]string, len(users))
					for i, u := range users {
						usersList[i] = u.(string)
					}
					c.updateUsersList(usersList)
				}
			case "files_list":
				if files, ok := data["files"].([]interface{}); ok {
					filesList := make([]string, len(files))
					for i, f := range files {
						filesList[i] = f.(string)
					}
					c.updateFilesList(filesList)
				}
			case "server_message":
				c.appendMessage(fmt.Sprintf("SERVER: %s", data["content"]))
				if data["content"] == "您已被服务器强制下线" {
					c.window.Close()
				}
			case "message":
				c.appendMessage(fmt.Sprintf("%s: %s", data["from"], data["content"]))
			}

		case 1: // 表情消息
			lenBuffer := make([]byte, 4)
			_, err := io.ReadFull(c.conn, lenBuffer)
			if err != nil {
				log.Printf("读取表情数据长度失败: %v", err)
				return
			}
			dataLen := binary.BigEndian.Uint32(lenBuffer)

			data := make([]byte, dataLen)
			_, err = io.ReadFull(c.conn, data)
			if err != nil {
				log.Printf("读取表情数据失败: %v", err)
				return
			}

			var emojiData map[string]interface{}
			if err := json.Unmarshal(data, &emojiData); err != nil {
				log.Printf("表情数据解析失败: %v", err)
				continue
			}

			if from, ok := emojiData["from"].(string); ok {
				c.appendMessage(fmt.Sprintf("%s: [表情]", from))
			}

		case 2: // 文件消息
			lenBuffer := make([]byte, 4)
			_, err := io.ReadFull(c.conn, lenBuffer)
			if err != nil {
				log.Printf("读取文件数据长度失败: %v", err)
				return
			}
			dataLen := binary.BigEndian.Uint32(lenBuffer)

			data := make([]byte, dataLen)
			_, err = io.ReadFull(c.conn, data)
			if err != nil {
				log.Printf("读取文件数据失败: %v", err)
				return
			}

			var fileData map[string]interface{}
			if err := json.Unmarshal(data, &fileData); err != nil {
				log.Printf("文件数据解析失败: %v", err)
				continue
			}

			if from, ok := fileData["from"].(string); ok {
				c.appendMessage(fmt.Sprintf("收到来自 %s 的文件: %s", from, fileData["filename"]))
			}
		}
	}

	dialog.ShowInformation("连接断开", "与服务器的连接已断开", c.window)
	c.window.Close()
}

func (c *Client) connect(username string) error {
	conn, err := net.Dial("tcp", "localhost:5000")
	if err != nil {
		return fmt.Errorf("连接服务器失败: %v", err)
	}

	c.conn = conn
	c.username = username

	// 发送用户名
	_, err = conn.Write([]byte(username))
	if err != nil {
		conn.Close()
		return fmt.Errorf("发送用户名失败: %v", err)
	}

	// 启动接收消息的协程
	go c.receiveMessages()

	// 添加连接成功的消息
	c.appendMessage(fmt.Sprintf("欢迎 %s 进入聊天室", username))

	return nil
}

func (c *Client) enableControls() {
	c.enabled = true
	c.msgInput.Enable()
	c.buttons.sendButton.Enable()
	c.buttons.fileButton.Enable()
	c.buttons.emojiButton.Enable()
	c.buttons.downloadButton.Enable()
}

func showLoginWindow(myApp fyne.App, onLogin func(username string)) {
	// 创建登录窗口
	loginWindow := myApp.NewWindow("登录")
	loginWindow.Resize(fyne.NewSize(300, 150))

	// 使用普通Entry
	usernameEntry := widget.NewEntry()
	usernameEntry.SetPlaceHolder("输入用户名")

	// 显示当前输入的用户名
	previewLabel := widget.NewLabel("")
	usernameEntry.OnChanged = func(text string) {
		previewLabel.SetText("当前输入: " + text)
	}

	loginButton := widget.NewButton("登录", func() {
		username := usernameEntry.Text
		if username == "" {
			dialog.ShowInformation("提示", "请输入用户名", loginWindow)
			return
		}
		loginWindow.Hide()
		onLogin(username)
	})

	loginContent := container.NewVBox(
		widget.NewLabel("用户名:"),
		usernameEntry,
		previewLabel,
		loginButton,
	)

	loginWindow.SetContent(container.NewPadded(loginContent))
	loginWindow.Show()
}

func main() {
	// 创建应用实例
	myApp := app.New()

	// 创建客户端
	client := NewClient()
	client.setupGUI(myApp)
	client.window.Hide() // 先隐藏主窗口

	// 显示登录窗口
	showLoginWindow(myApp, func(username string) {
		// 连接服务器
		err := client.connect(username)
		if err != nil {
			dialog.ShowError(err, client.window)
			myApp.Quit()
			return
		}

		// 启用控件
		client.enableControls()

		// 显示主窗口
		client.window.Show()
	})

	// 运行应用
	myApp.Run()
}
