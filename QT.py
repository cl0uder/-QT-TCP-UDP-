from PySide6.QtWidgets import QApplication
from PySide6.QtUiTools import QUiLoader
from socket import *
import cv2
import pyaudio
import threading
import numpy as np


# 设置音频流参数
CHUNK = 1024  # 每次读出的音频数据块大小
FORMAT = pyaudio.paInt16  # 音频格式
CHANNELS = 1  # 声道数（单声道）
RATE = 44100  # 采样率

uiLoader = QUiLoader()


class Stats:

    def __init__(self):
        # 从文件中加载UI定义

        # 从 UI 定义中动态 创建一个相应的窗口对象
        # 注意：里面的控件对象也成为窗口对象的属性了
        # 比如 self.ui.button , self.ui.textEdit
        self.ui = QUiLoader().load('main.ui')
        self.ui.listWidget.itemSelectionChanged.connect(
            self.opItemsChange
        )
        self.ui.Btn_TCP_server.clicked.connect(
            self.TCPconnect_server
        )
        self.ui.Btn_TCP_client.clicked.connect(
            self.TCPconnect_client
        )
        self.ui.Btn_UDP_server.clicked.connect(
            self.UDPconnect_server
        )
        self.ui.Btn_UDP_client.clicked.connect(
            self.UDPconnect_client
        )
        self.ui.Btn_AUDIO_device.clicked.connect(
            self.Btn_AUDIO_device
        )
        self.listenSocket = None
        self.dataSocket = None
        self.client_video_socket = None
        self.client_audio_socket = None

    def opItemsChange(self):
        option = self.ui.listWidget.currentItem().text()

        pageIdxTable = {
            "UDP客户端": 0,
            "UDP服务端": 1,
            "TCP客户端": 2,
            "TCP服务端": 3,
            "音频设备": 4,
        }

        idx = pageIdxTable.get(option)
        if idx is None:
            return

        self.ui.stackedWidget.setCurrentIndex(idx)
        if option == "UDP客户端":
            self.ui.stackedWidget.setCurrentIndex(0)
        elif option == "UDP服务端":
            self.ui.stackedWidget.setCurrentIndex(1)
        elif option == "TCP客户端":
            self.ui.stackedWidget.setCurrentIndex(2)
        elif option == "TCP服务端":
            self.ui.stackedWidget.setCurrentIndex(3)
        elif option == "音频设备":
            self.ui.stackedWidget.setCurrentIndex(4)



    def TCPconnect_server(self):
        # 创建tcp服务端socket
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        IP = self.ui.input_TCPserverIP.text()
        PORT = self.ui.input_TCPserverPort.text()
        # 设置TCP缓冲区大小
        self.server_socket.setsockopt(SOL_SOCKET, SO_SNDBUF, 4096)
        self.server_socket.setsockopt(SOL_SOCKET, SO_RCVBUF, 4096)
        # 禁用Nagle算法，减少小数据包的传输延迟
        self.server_socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        # socket绑定地址和端口
        self.server_socket.bind((IP, int(PORT)))
        self.server_socket.listen(8)
        self._log('服务端启动成功，在等待客户端连接...')
        threading.Thread(target=self.accept_clients).start()

    def accept_clients(self):
        while True:
            try:
                # 接收客户端信息
                conn, addr = self.server_socket.accept()
                self._log(f"连接来自 {addr}")
                # 接收下载信息
                file_name_data = conn.recv(1024)
                if not file_name_data:
                    conn.close()
                    continue
                file_name = file_name_data.decode()
                if file_name == 'upload':
                    # 接收客户端上传文件
                    with open('server_upload.txt', 'wb') as f:
                        while True:
                            file_data = conn.recv(1024)
                            if not file_data:
                                break
                            f.write(file_data)
                            # 输出文件内容
                    with open('server_upload.txt', 'r') as f:
                        file_content = f.read()
                        self._log(f"文件内容：\n{file_content}")
                    self._log('文件上传成功！')
                if file_name == 'download':
                    # 发送文件给客户端
                    with open('server_upload.txt', 'rb') as f:
                        file_data = f.read()
                        conn.sendall(file_data)
                    with open('server_upload.txt', 'r') as f:
                        file_content = f.read()
                        self._log(f"文件内容：\n{file_content}")
                    self._log('文件发送成功！')


                # 关闭连接
                conn.close()
            except socket.error as e:
                self._log(f"Socket error: {e}")
            except Exception as e:
                self._log(f"Unexpected error: {e}")


    def _log(self, msg):
        self.ui.msgWindow.append(msg)
        self.ui.msgWindow.ensureCursorVisible()

    def TCPconnect_client(self):
        # 实例化一个socket对象，指明协议
        self.client_socket = socket(AF_INET, SOCK_STREAM)
        self.client_socket.settimeout(2)

        IP = self.ui.input_TCPclientIP.text()
        SERVER_PORT = self.ui.input_TCPclientPort.text()

        self.client_socket.connect((IP, int(SERVER_PORT)))
        self._log('连接成功')
        # 请求上传文件
        self.client_socket.send('upload'.encode())
        # 上传文件
        with open('client_upload.txt', 'rb') as f:
            file_data = f.read()
            self.client_socket.sendall(file_data)
        with open('client_upload.txt', 'r') as f:
            file_content = f.read()
            self._log(f"文件内容：\n{file_content}")
        self._log('文件上传成功！')

        # 请求下载文件
        self.client_socket.send('download'.encode())

        # 接收文件
        with open('client_download.txt', 'wb') as f:
            while True:
                file_data = self.client_socket.recv(1024)
                if not file_data:
                    break
                f.write(file_data)
        with open('client_upload.txt', 'r') as f:
            file_content = f.read()
            self._log(f"文件内容：\n{file_content}")
        self._log('文件下载成功！')


    def send_video(self):
        SERVER_IP = self.ui.input_UDPclientIP.text()
        SERVER_PORT_VIDEO = self.ui.UDPclient_VIDEOPORT.text()  # 视频端口
        BUFFER_SIZE = 65507
        """发送视频数据的线程函数"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self._log('无法打开摄像头')
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 压缩视频帧为JPEG格式
            encoded, buffer = cv2.imencode('.jpg', frame)
            data = buffer.tobytes()

            # 分片传输视频数据
            for i in range(0, len(data), BUFFER_SIZE):
                packet = data[i:i + BUFFER_SIZE]
                self.client_video_socket.sendto(packet, (SERVER_IP, int(SERVER_PORT_VIDEO)))

            cv2.imshow("Client - Sending Video", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def send_audio(self):
        SERVER_IP = self.ui.input_UDPclientIP.text()
        SERVER_PORT_AUDIO = self.ui.UDPclient_AUDIOPORT.text()  # 音频端口
        input_device_index = self.ui.UDPclient_AUDIODEVICE.text()

        # 初始化PyAudio
        p = pyaudio.PyAudio()
        input_audio_stream = p.open(format=FORMAT,
                                    channels=CHANNELS,
                                    rate=RATE,
                                    input=True,
                                    frames_per_buffer=CHUNK,
                                    input_device_index=int(input_device_index))
        """发送音频数据的线程函数"""
        while True:
            audio_data = input_audio_stream.read(CHUNK)
            self.client_audio_socket.sendto(audio_data, (SERVER_IP, int(SERVER_PORT_AUDIO)))

    def UDPconnect_client(self):
        # 创建UDP套接字
        self.client_video_socket = socket(AF_INET, SOCK_DGRAM)
        self.client_audio_socket = socket(AF_INET, SOCK_DGRAM)
        self.client_video_socket.settimeout(2)
        self.client_audio_socket.settimeout(2)

        input_device_index = self.ui.UDPclient_AUDIODEVICE.text()

        # 初始化PyAudio
        p = pyaudio.PyAudio()
        input_audio_stream = p.open(format=FORMAT,
                                    channels=CHANNELS,
                                    rate=RATE,
                                    input=True,
                                    frames_per_buffer=CHUNK,
                                    input_device_index=int(input_device_index))
        # 启动视频和音频传输线程
        video_thread = threading.Thread(target=lambda: self.send_video())
        audio_thread = threading.Thread(target=lambda: self.send_audio())

        video_thread.start()
        audio_thread.start()

        video_thread.join()
        audio_thread.join()

        # 关闭音频流
        input_audio_stream.stop_stream()
        input_audio_stream.close()
        p.terminate()

        self.client_video_socket.close()
        self.client_audio_socket.close()

    def UDPconnect_server(self):
        SERVER_IP_VIDEO = self.ui.input_UDPserverIP.text()  # 视频数据监听IP地址
        SERVER_PORT_VIDEO = self.ui.UDPserver_VIDEOPORT.text()  # 视频端口
        SERVER_IP_AUDIO = self.ui.input_UDPserverIP.text()  # 音频数据监听IP地址
        SERVER_PORT_AUDIO = self.ui.UDPserver_AUDIOPORT.text()  # 音频端口
        output_device_index = self.ui.UDPserver_AUDIODEVICE.text()
        BUFFER_SIZE = 65507  # UDP数据包的最大大小

        # 初始化PyAudio
        p = pyaudio.PyAudio()
        output_audio_stream = p.open(format=FORMAT,
                                     channels=CHANNELS,
                                     rate=RATE,
                                     output=True,
                                     output_device_index=int(output_device_index))

        # 创建UDP套接字
        server_socket_video = socket(AF_INET, SOCK_DGRAM)
        server_socket_video.bind((SERVER_IP_VIDEO, int(SERVER_PORT_VIDEO)))

        server_socket_audio = socket(AF_INET, SOCK_DGRAM)
        server_socket_audio.bind((SERVER_IP_AUDIO, int(SERVER_PORT_AUDIO)))
        self._log('服务器正在等待视频和音频数据...')

        while True:
            # 接收视频数据
            data_video = b""
            while True:
                packet_video, addr_video = server_socket_video.recvfrom(BUFFER_SIZE)
                data_video += packet_video
                if len(packet_video) < BUFFER_SIZE:
                    break  # 说明最后一个包已到达

            # 将数据解码为图像
            np_data_video = np.frombuffer(data_video, dtype=np.uint8)
            frame = cv2.imdecode(np_data_video, cv2.IMREAD_COLOR)

            if frame is not None:
                # 显示接收到的帧
                cv2.imshow('Server - Receiving Video', frame)

            # 接收音频数据
            data_audio = b""
            while True:
                packet_audio, addr_audio = server_socket_audio.recvfrom(BUFFER_SIZE)
                data_audio += packet_audio
                if len(packet_audio) < BUFFER_SIZE:
                    break  # 说明最后一个包已到达

            # 播放音频数据
            output_audio_stream.write(data_audio)
            # 按 'q' 键退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # 释放资源
        cv2.destroyAllWindows()
        output_audio_stream.stop_stream()
        output_audio_stream.close()
        p.terminate()
        server_socket_video.close()
        server_socket_audio.close()

    def Btn_AUDIO_device(self):
        # 初始化PyAudio
        p = pyaudio.PyAudio()

        # 列出所有音频设备信息
        info = p.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')

        # 打印所有音频设备的索引和名称
        for i in range(0, num_devices):
            device_info = p.get_device_info_by_host_api_device_index(0, i)
            self._log(f"Device Index: {device_info.get('index')}, Device Name: {device_info.get('name')}")


app = QApplication([])
stats = Stats()
stats.ui.show()
app.exec()  # PySide6 是 exec 而不是 exec_