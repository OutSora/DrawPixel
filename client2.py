import socket
import threading
import pickle
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog
from PIL import Image, ImageTk
import io


class PixelBattleClient:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.current_color = "#000000"
        self.remaining_time = 300  # 5 minutes
        self.setup_gui()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("DrawPixel")
        self.root.configure(bg='#333333')  # Темно-серый фон

        # Timer label
        self.timer_label = tk.Label(self.root, text="Времени осталось: 5:00", font=('Arial', 14), bg='#333333',
                                    fg='white')
        self.timer_label.pack(pady=5)

        # Color selection
        color_frame = tk.Frame(self.root, bg='#333333')
        color_frame.pack(pady=5)

        self.color_btn = tk.Button(color_frame, text="Выбрать цвет", command=self.choose_color)
        self.color_btn.pack(side=tk.LEFT, padx=5)

        self.color_preview = tk.Canvas(color_frame, width=30, height=30)
        self.color_preview.pack(side=tk.LEFT)
        self.update_color_preview()

        # Canvas
        self.canvas_size = 500
        self.pixel_size = 10
        self.canvas = tk.Canvas(self.root, width=self.canvas_size, height=self.canvas_size, bg='white')
        self.canvas.pack(pady=10)
        self.canvas.bind('<Button-1>', self.canvas_click)

        # Chat setup
        self.setup_chat()

        self.draw_grid()

        # Buttons frame
        buttons_frame = tk.Frame(self.root, bg='#333333')
        buttons_frame.pack(pady=5)

        # Connect button
        self.connect_btn = tk.Button(buttons_frame, text="Присоединиться к серверу", command=self.connect_to_server)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Save button
        self.save_btn = tk.Button(buttons_frame, text="Сохранить изображеие", command=self.request_save)
        self.save_btn.pack(side=tk.LEFT, padx=5)

    def setup_chat(self):
        # Создаем фрейм для чата
        chat_frame = tk.Frame(self.root, bg='#333333')
        chat_frame.pack(pady=5, fill=tk.BOTH, expand=True)

        # Область сообщений
        self.chat_area = tk.Text(chat_frame, height=10, width=50, state='disabled', bg='#444444', fg='white')
        self.chat_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Поле ввода сообщения
        message_frame = tk.Frame(chat_frame, bg='#333333')
        message_frame.pack(fill=tk.X, pady=5)

        self.message_entry = tk.Entry(message_frame, bg='#444444', fg='white', insertbackground='white')
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', self.send_chat_message)

        send_button = tk.Button(message_frame, text="Отправить", command=self.send_chat_message)
        send_button.pack(side=tk.RIGHT, padx=5)

    def send_chat_message(self, event=None):
        message = self.message_entry.get().strip()
        if message and hasattr(self, 'connected') and self.connected:
            self.send_message({
                'type': 'chat',
                'data': message
            })
            self.message_entry.delete(0, tk.END)

    def add_chat_message(self, username, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, f"{username}: {message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    def update_timer_display(self, remaining):
        self.remaining_time = remaining
        minutes = remaining // 60
        seconds = remaining % 60
        self.timer_label.config(text=f"Time remaining: {minutes}:{seconds:02d}")
        if remaining <= 0:
            self.timer_label.config(text="Time's up!")

    def draw_grid(self):
        for i in range(0, self.canvas_size, self.pixel_size):
            self.canvas.create_line(i, 0, i, self.canvas_size, fill='gray')
            self.canvas.create_line(0, i, self.canvas_size, i, fill='gray')

    def choose_color(self):
        color = colorchooser.askcolor(color=self.current_color)[1]
        if color:
            self.current_color = color
            self.update_color_preview()

    def update_color_preview(self):
        self.color_preview.delete("all")
        self.color_preview.create_rectangle(0, 0, 30, 30, fill=self.current_color)

    def canvas_click(self, event):
        if not hasattr(self, 'connected') or not self.connected:
            messagebox.showwarning("Нет подкючения", "Для начала присоединись к серверу")
            return

        x = event.x // self.pixel_size
        y = event.y // self.pixel_size

        if 0 <= x < 50 and 0 <= y < 50:
            self.send_message({
                'type': 'pixel',
                'data': (x, y, self.current_color)
            })

    def connect_to_server(self):
        username = simpledialog.askstring("Ник", "Введите имя пользователя:")
        if not username:
            return

        try:
            self.socket.connect((self.host, self.port))
            self.username = username
            self.connected = True
            self.connect_btn.config(state=tk.DISABLED)

            self.send_message({
                'type': 'signup',
                'data': username
            })

            threading.Thread(target=self.receive_messages, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")

    def send_message(self, message):
        try:
            self.socket.send(pickle.dumps(message))
        except Exception as e:
            messagebox.showerror("Error", f"Could not send message: {e}")

    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break

                message = pickle.loads(data)
                self.handle_message(message)

            except Exception as e:
                print(f"Error receiving message: {e}")
                break

        self.socket.close()
        self.connected = False

    def handle_message(self, message):
        msg_type = message.get('type')
        data = message.get('data')

        if msg_type == 'pixel_update':
            x, y, color = data
            self.update_pixel(x, y, color)

        elif msg_type == 'canvas_state':
            for x, y, color in data:
                self.update_pixel(x, y, color)

        elif msg_type == 'time_update':
            self.update_timer_display(data)

        elif msg_type == 'game_end':
            messagebox.showinfo("Game Over", "Время вышло. Игра окончена")
            self.remaining_time = 0

        elif msg_type == 'final_image':
            self.save_final_image(data)

        elif msg_type == 'chat':
            username, message = data
            self.add_chat_message(username, message)

    def update_pixel(self, x, y, color):
        x1 = x * self.pixel_size
        y1 = y * self.pixel_size
        x2 = x1 + self.pixel_size
        y2 = y1 + self.pixel_size

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='')

    def request_save(self):
        if hasattr(self, 'connected') and self.connected:
            self.send_message({
                'type': 'save',
                'data': None
            })
        else:
            messagebox.showwarning("Нет подключения", "Для начала присоединись к серверу")

    def save_final_image(self, image_data):
        try:
            image = Image.open(io.BytesIO(image_data))
            image.save(f"battle_result_{self.username}.png")
            messagebox.showinfo("Отлично", "Картинка была сохранена")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Картинка не сохранилась: {e}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    client = PixelBattleClient()
    client.run()
