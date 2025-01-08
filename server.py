import socket
import threading
import pickle
import time
from PIL import Image
import io
from datetime import datetime


class PixelBattleServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.clients = {}  # {client_socket: username}
        self.canvas = [[None for _ in range(50)] for _ in range(50)]
        self.game_duration = 300  # 5 minutes
        self.start_time = None
        self.game_active = False
        self.lock = threading.Lock()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

    def start(self):
        print(f"Server started on {self.host}:{self.port}")
        self.game_active = True
        self.start_time = time.time()
        threading.Thread(target=self.game_timer).start()
        threading.Thread(target=self.broadcast_time).start()

        while True:
            client_socket, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def broadcast_time(self):
        while self.game_active:
            elapsed = int(time.time() - self.start_time)
            remaining = max(0, self.game_duration - elapsed)

            self.broadcast_message({
                'type': 'time_update',
                'data': remaining
            })
            time.sleep(1)

    def game_timer(self):
        time.sleep(self.game_duration)
        self.game_active = False
        self.save_canvas()
        self.broadcast_game_end()

    def handle_client(self, client_socket):
        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break

                message = pickle.loads(data)
                self.process_message(client_socket, message)

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            self.remove_client(client_socket)

    def process_message(self, client_socket, message):
        msg_type = message.get('type')
        data = message.get('data')

        if msg_type == 'signup':
            username = data
            if username not in self.clients.values():
                self.clients[client_socket] = username
                self.send_canvas_state(client_socket)

                # Send current time to new client
                elapsed = int(time.time() - self.start_time)
                remaining = max(0, self.game_duration - elapsed)
                client_socket.send(pickle.dumps({
                    'type': 'time_update',
                    'data': remaining
                }))

                self.broadcast_message({
                    'type': 'chat',
                    'data': ('DrawPixel', f'{username} присоединился к игре')
                })

        elif msg_type == 'pixel':
            if self.game_active:
                x, y, color = data
                with self.lock:
                    self.canvas[y][x] = color
                self.broadcast_message({
                    'type': 'pixel_update',
                    'data': (x, y, color)
                })

        elif msg_type == 'save':
            self.save_canvas()

        elif msg_type == 'chat':
            if client_socket in self.clients:
                username = self.clients[client_socket]
                self.broadcast_message({
                    'type': 'chat',
                    'data': (username, data)
                })

    def send_canvas_state(self, client_socket):
        canvas_state = []
        for y in range(50):
            for x in range(50):
                color = self.canvas[y][x]
                if color:
                    canvas_state.append((x, y, color))

        try:
            client_socket.send(pickle.dumps({
                'type': 'canvas_state',
                'data': canvas_state
            }))
        except:
            pass

    def save_canvas(self):
        img = Image.new('RGB', (50, 50), 'white')
        pixels = img.load()

        for y in range(50):
            for x in range(50):
                color = self.canvas[y][x]
                if color:
                    pixels[x, y] = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"battle_{timestamp}.png"
        img.save(filename)

        with open(filename, 'rb') as f:
            image_data = f.read()
            self.broadcast_message({
                'type': 'final_image',
                'data': image_data
            })

    def broadcast_message(self, message):
        for client in self.clients.keys():
            try:
                client.send(pickle.dumps(message))
            except:
                pass

    def broadcast_game_end(self):
        self.broadcast_message({
            'type': 'game_end',
            'data': None
        })

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]
            del self.clients[client_socket]
            self.broadcast_message({
                'type': 'chat',
                'data': ('DrawPixel', f'{username} покинул игру')
            })
        client_socket.close()


if __name__ == '__main__':
    server = PixelBattleServer()
    server.start()
