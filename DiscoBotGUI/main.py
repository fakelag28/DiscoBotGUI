import tkinter as tk
import asyncio
import threading
from discord.ext import commands
import discord
import aiohttp
from PIL import Image, ImageTk, ImageDraw
import io
from tkinter import ttk

TOKEN = '' # Сюда вы можете вставить токен, который будет использоваться при авторизации с пустым полем для ввода

class AuthWindow:
    def __init__(self, root, on_auth):
        self.root = root
        self.on_auth = on_auth
        self.root.title('DiscoBotGUI - Авторизация')
        self.root.geometry('300x150')
        self.token = None
        self.frame = tk.Frame(self.root, bg='#36393f')
        self.frame.pack(expand=True, fill='both')
        self.label = tk.Label(self.frame, text='Введите токен бота:', bg='#36393f', fg='white', font=('Segoe UI', 12))
        self.label.pack(pady=10)
        self.entry = tk.Entry(self.frame, show='*', width=30, font=('Segoe UI', 11), bg='#23272a', fg='white', insertbackground='white', relief='flat')
        self.entry.pack(pady=5)
        self.button = tk.Button(self.frame, text='Авторизация', command=self.authorize, bg='#7289da', fg='white', font=('Segoe UI', 11), relief='flat', activebackground='#5865f2')
        self.button.pack(pady=10)
        self.root.bind('<Return>', lambda event: self.authorize())
    def authorize(self):
        self.token = self.entry.get().strip()
        if self.token:
            self.on_auth(self.token)
        else:
            self.on_auth(TOKEN)

class DiscordBot(commands.Bot):
    def __init__(self, gui, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gui = gui
    async def on_ready(self):
        self.gui.on_bot_ready()

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.widget.bind('<Enter>', self.show)
        self.widget.bind('<Leave>', self.hide)
    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 50
        y = self.widget.winfo_rooty() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f'+{x}+{y}')
        label = tk.Label(tw, text=self.text, justify='left', background='#23272a', fg='white', relief='solid', borderwidth=1, font=('Segoe UI', 10))
        label.pack(ipadx=8, ipady=2)
    def hide(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class MainGUI:
    def __init__(self, token):
        self.root = tk.Tk()
        self.root.title('DiscoBotGUI')
        self.root.geometry('1000x700')
        self.root.resizable(False, False)
        self.token = token
        self.servers = []
        self.channels = []
        self.channel_objs = []
        self.messages = []
        self.selected_guild = None
        self.selected_channel = None
        self.guild_avatars = {}
        self.guild_avatar_widgets = []
        self.ready = False
        self.message_limit = 100
        self.setup_layout()
        self.loop = asyncio.new_event_loop()
        self.bot = DiscordBot(self, command_prefix='!', intents=discord.Intents.all(), loop=self.loop)
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()
    def setup_layout(self):
        self.left_frame = tk.Frame(self.root, width=80, bg='#23272a')
        self.left_frame.pack(side='left', fill='y')
        self.left_frame.pack_propagate(False)
        self.left_separator = tk.Frame(self.root, width=2, bg='#202225')
        self.left_separator.pack(side='left', fill='y')
        self.center_frame = tk.Frame(self.root, width=220, bg='#2c2f33')
        self.center_frame.pack(side='left', fill='y')
        self.center_frame.pack_propagate(False)
        self.center_separator = tk.Frame(self.root, width=2, bg='#202225')
        self.center_separator.pack(side='left', fill='y')
        self.right_frame = tk.Frame(self.root, bg='#36393f')
        self.right_frame.pack(side='left', fill='both', expand=True)
        self.guilds_top = tk.Frame(self.left_frame, bg='#23272a')
        self.guilds_top.pack(fill='x', padx=0, pady=(0, 2))
        self.refresh_btn = tk.Button(self.guilds_top, text='⟳', command=self.update_servers, bg='#23272a', fg='white', font=('Segoe UI', 14), relief='flat', activebackground='#36393f', width=2, height=1, bd=0, highlightthickness=0)
        self.refresh_btn.pack(side='top', pady=4)
        self.guilds_canvas = tk.Canvas(self.left_frame, bg='#23272a', highlightthickness=0, borderwidth=0, width=80)
        self.guilds_canvas.pack(fill='both', expand=True, side='left')
        self.guilds_scrollbar = ttk.Scrollbar(self.left_frame, orient='vertical', command=self.guilds_canvas.yview, style='Vertical.TScrollbar')
        self.guilds_scrollbar.pack(side='right', fill='y')
        self.guilds_canvas.configure(yscrollcommand=self.guilds_scrollbar.set)
        self.guilds_frame = tk.Frame(self.guilds_canvas, bg='#23272a')
        self.guilds_canvas.create_window((0, 0), window=self.guilds_frame, anchor='nw')
        self.guilds_frame.bind('<Configure>', lambda e: self.guilds_canvas.configure(scrollregion=self.guilds_canvas.bbox('all')))
        self.guilds_canvas.bind('<Enter>', lambda e: self._bind_mousewheel(self.guilds_canvas, self._on_guilds_mousewheel))
        self.guilds_canvas.bind('<Leave>', lambda e: self._unbind_mousewheel(self.guilds_canvas))
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Treeview', background='#2c2f33', fieldbackground='#2c2f33', foreground='white', borderwidth=0, font=('Segoe UI', 10), rowheight=28, relief='flat')
        style.configure('Treeview.Item', background='#2c2f33', foreground='white')
        style.map('Treeview', background=[('selected', '#5865f2')], foreground=[('selected', 'white')])
        self.channel_tree = ttk.Treeview(self.center_frame, show='tree', selectmode='browse', style='Treeview')
        self.channel_tree.pack(fill='both', expand=True, padx=0, pady=0, side='left')
        dark_scrollbar_style = ttk.Style()
        dark_scrollbar_style.theme_use('default')
        dark_scrollbar_style.configure('Vertical.TScrollbar',
            gripcount=0,
            background='#202225',
            darkcolor='#23272a',
            lightcolor='#23272a',
            troughcolor='#2c2f33',
            bordercolor='#23272a',
            arrowcolor='#b9bbbe',
            relief='flat',
            borderwidth=0
        )
        self.channel_scrollbar = ttk.Scrollbar(self.center_frame, orient='vertical', command=self.channel_tree.yview, style='Vertical.TScrollbar')
        self.channel_tree.config(yscrollcommand=self.channel_scrollbar.set)
        self.channel_tree.bind('<<TreeviewSelect>>', self.on_channel_select)
        self.channel_tree.bind('<Button-3>', self.on_channel_right_click)
        self.guild_name_label = tk.Label(self.center_frame, text='', bg='#2c2f33', fg='white', font=('Segoe UI', 12, 'bold'), anchor='w')
        self.guild_name_label.pack(fill='x', padx=8, pady=(8, 2))
        self.chat_frame = tk.Frame(self.right_frame, bg='#36393f')
        self.chat_frame.pack(fill='both', expand=True, padx=0, pady=0)
        self.load_more_btn = tk.Button(self.chat_frame, text='Загрузить ещё сообщений...', command=self.load_more_messages, bg='#23272a', fg='white', font=('Segoe UI', 10), relief='flat', activebackground='#36393f')
        self.load_more_btn.pack(side='top', pady=(8, 8))
        self.chat_canvas = tk.Canvas(self.chat_frame, bg='#36393f', highlightthickness=0, borderwidth=0)
        self.chat_canvas.pack(fill='both', expand=True, side='left')
        self.chat_scrollbar = ttk.Scrollbar(self.chat_frame, orient='vertical', command=self.chat_canvas.yview, style='Vertical.TScrollbar')
        self.chat_scrollbar.pack(side='right', fill='y')
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.messages_frame = tk.Frame(self.chat_canvas, bg='#36393f')
        self.chat_canvas.create_window((0, 0), window=self.messages_frame, anchor='nw')
        self.messages_frame.bind('<Configure>', lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox('all')))
        self.chat_canvas.bind('<Enter>', lambda e: self._bind_mousewheel(self.chat_canvas, self._on_chat_mousewheel))
        self.chat_canvas.bind('<Leave>', lambda e: self._unbind_mousewheel(self.chat_canvas))
        self.input_frame = tk.Frame(self.right_frame, bg='#23272a')
        self.input_frame.pack(fill='x', side='bottom', padx=0, pady=0)
        self.message_entry = tk.Entry(self.input_frame, font=('Segoe UI', 11), bg='#36393f', fg='white', insertbackground='white', relief='flat')
        self.message_entry.pack(side='left', fill='x', expand=True, padx=(10, 0), pady=10)
        self.send_btn = tk.Button(self.input_frame, text='Отправить', command=self.send_message, bg='#5865f2', fg='white', font=('Segoe UI', 11), relief='flat', activebackground='#7289da')
        self.send_btn.pack(side='left', padx=10, pady=10)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
    def _bind_mousewheel(self, widget, func):
        widget.bind_all('<MouseWheel>', func)
        widget.bind_all('<Button-4>', func)
        widget.bind_all('<Button-5>', func)
    def _unbind_mousewheel(self, widget):
        widget.unbind_all('<MouseWheel>')
        widget.unbind_all('<Button-4>')
        widget.unbind_all('<Button-5>')
    def _on_guilds_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.guilds_canvas.yview_scroll(-1, 'units')
        elif event.num == 5 or event.delta < 0:
            self.guilds_canvas.yview_scroll(1, 'units')
    def _on_chat_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.chat_canvas.yview_scroll(-1, 'units')
        elif event.num == 5 or event.delta < 0:
            self.chat_canvas.yview_scroll(1, 'units')
    def run_bot(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.bot.start(self.token))
        except Exception as e:
            pass
    def on_bot_ready(self):
        self.ready = True
        self.root.after(0, self.update_servers)
    def update_servers(self):
        if not self.ready:
            return
        self.servers = list(self.bot.guilds)
        asyncio.run_coroutine_threadsafe(self.load_guild_avatars(), self.loop)
        self.update_guilds_panel()
        if self.servers:
            self.select_guild(0)
        else:
            self.guild_name_label.config(text='')
    def update_guilds_panel(self):
        for widget in self.guilds_frame.winfo_children():
            widget.destroy()
        self.guild_avatar_widgets.clear()
        for idx, g in enumerate(self.servers):
            avatar = self.guild_avatars.get(g.id)
            borderwidth = 3 if self.selected_guild and g.id == self.selected_guild.id else 0
            highlightcolor = '#5865f2' if self.selected_guild and g.id == self.selected_guild.id else '#23272a'
            btn = tk.Label(self.guilds_frame, image=avatar if avatar else None, bg='#23272a', width=56, height=56, cursor='hand2',
                          highlightthickness=borderwidth, highlightbackground=highlightcolor)
            if not avatar:
                btn.config(bg='#36393f')
            btn.grid(row=idx, column=0, pady=8, padx=12)
            btn.bind('<Button-1>', lambda e, i=idx: self.select_guild(i))
            btn.bind('<Button-3>', lambda e, g=g: self.on_guild_right_click(e, g))
            Tooltip(btn, g.name)
            self.guild_avatar_widgets.append(btn)
    def select_guild(self, idx):
        self.selected_guild = self.servers[idx]
        self.guild_name_label.config(text=self.selected_guild.name)
        self.channel_objs = [c for c in self.selected_guild.channels if isinstance(c, discord.TextChannel)]
        self.update_guilds_panel()
        self.update_channel_tree()
        if self.channel_objs:
            first_id = self.channel_objs[0].id
            for iid in self.channel_tree.get_children():
                for cid in self.channel_tree.get_children(iid):
                    self.channel_tree.selection_set(cid)
                    self.on_channel_select()
                    return
    def update_channel_tree(self):
        self.channel_tree.delete(*self.channel_tree.get_children())
        categories = {}
        for c in self.selected_guild.channels:
            if isinstance(c, discord.CategoryChannel):
                categories[c.id] = c
        cat_items = {}
        for cat_id, cat in categories.items():
            cat_items[cat_id] = self.channel_tree.insert('', 'end', text=cat.name, open=True)
        for c in self.selected_guild.channels:
            if isinstance(c, discord.TextChannel):
                parent = cat_items.get(c.category_id, '')
                self.channel_tree.insert(parent, 'end', text='# ' + c.name, iid=str(c.id))
        self.channel_tree.selection_set('')
    def on_channel_select(self, event=None):
        sel = self.channel_tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            cid = int(iid)
        except ValueError:
            return
        self.selected_channel = next((c for c in self.channel_objs if c.id == cid), None)
        self.message_limit = 100
        asyncio.run_coroutine_threadsafe(self.load_messages(), self.loop)
    def on_channel_right_click(self, event):
        item = self.channel_tree.identify_row(event.y)
        if not item:
            return
        try:
            cid = int(item)
        except ValueError:
            return
        channel = next((c for c in self.channel_objs if c.id == cid), None)
        if not channel:
            return
        menu = tk.Menu(self.root, tearoff=0, bg='#23272a', fg='white', activebackground='#5865f2', activeforeground='white')
        menu.add_command(label='Скопировать ID канала', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(str(channel.id))))
        menu.add_command(label='Скопировать ссылку на канал', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(f'https://discord.com/channels/{self.selected_guild.id}/{channel.id}')))
        menu.add_command(label='Скопировать название канала', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(channel.name)))
        menu.tk_popup(event.x_root, event.y_root)
    def on_guild_right_click(self, event, guild):
        menu = tk.Menu(self.root, tearoff=0, bg='#23272a', fg='white', activebackground='#5865f2', activeforeground='white')
        menu.add_command(label='Скопировать ID сервера', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(str(guild.id))))
        menu.add_command(label='Скопировать ссылку на сервер', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(f'https://discord.com/channels/{guild.id}')))
        menu.add_command(label='Скопировать название сервера', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(guild.name)))
        menu.tk_popup(event.x_root, event.y_root)
    async def load_guild_avatars(self):
        session = aiohttp.ClientSession()
        for g in self.servers:
            if g.id in self.guild_avatars:
                continue
            url = g.icon.url if g.icon else None
            if url:
                try:
                    data = await (await session.get(url)).read()
                    image = Image.open(io.BytesIO(data)).resize((56, 56))
                    mask = Image.new('L', (56, 56), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, 56, 56), fill=255)
                    image = image.convert('RGBA')
                    image.putalpha(mask)
                    self.guild_avatars[g.id] = ImageTk.PhotoImage(image)
                except Exception:
                    self.guild_avatars[g.id] = None
            else:
                self.guild_avatars[g.id] = None
        await session.close()
        self.root.after(0, self.update_guilds_panel)
    async def load_messages(self):
        if not self.selected_channel:
            self.messages = []
            self.root.after(0, self.update_message_listbox)
            return
        messages = []
        try:
            bot_user_id = self.bot.user.id if self.bot.user else None
            async for msg in self.selected_channel.history(limit=self.message_limit):
                msg_data = {
                    'author': msg.author.display_name,
                    'content': msg.content,
                    'embeds': [],
                    'id': msg.id,
                    'author_id': msg.author.id,
                    'is_bot': (msg.author.id == bot_user_id),
                    'discord_name': getattr(msg.author, 'name', None),
                    'created_at': msg.created_at,
                    'attachments': [{'url': a.url} for a in getattr(msg, 'attachments', [])]
                }
                if msg.embeds:
                    for emb in msg.embeds:
                        msg_data['embeds'].append({
                            'title': emb.title if hasattr(emb, 'title') else '',
                            'description': emb.description if hasattr(emb, 'description') else '',
                            'url': emb.url if hasattr(emb, 'url') else '',
                            'image_url': emb.image.url if hasattr(emb, 'image') and emb.image else ''
                        })
                messages.append(msg_data)
        except Exception:
            messages = [{'author': '', 'content': 'Ошибка загрузки сообщений', 'embeds': [], 'id': 0, 'author_id': 0, 'is_bot': False}]
        self.messages = list(reversed(messages))
        self.root.after(0, self.update_message_listbox)
    def load_more_messages(self):
        self.message_limit += 100
        asyncio.run_coroutine_threadsafe(self.load_messages(), self.loop)
    def update_message_listbox(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        for idx, m in enumerate(self.messages):
            if m.get('is_bot'):
                frame_bg = '#5865f2'
            else:
                frame_bg = '#23272a' if m.get('is_bot') else '#36393f'
            frame = tk.Frame(self.messages_frame, bg=frame_bg)
            frame.pack(fill='x', anchor='w', pady=2, padx=10)
            top_row = tk.Frame(frame, bg=frame_bg)
            top_row.pack(fill='x', anchor='w')
            display_name = m['author']
            discord_name = m.get('discord_name', None)
            msg_time = m.get('created_at', None)
            time_str = ''
            if msg_time:
                time_str = msg_time.strftime('%d.%m.%Y %H:%M')
            if discord_name and discord_name != display_name:
                display_name = f"{display_name} ({discord_name}, {time_str})"
            else:
                display_name = f"{display_name} ({time_str})"
            name_label = tk.Label(top_row, text=display_name, font=('Segoe UI', 10, 'bold'), fg='#fff', bg=frame_bg, anchor='w')
            name_label.pack(side='left', anchor='w')
            more_icon = tk.Label(top_row, text='⋮', font=('Segoe UI', 12), fg='#b9bbbe', bg=frame_bg, cursor='hand2')
            more_icon.pack(side='left', anchor='w', padx=6)
            def on_enter(e, w=more_icon): w.config(bg='#23272a', fg='#fff')
            def on_leave(e, w=more_icon): w.config(bg=frame_bg, fg='#b9bbbe')
            more_icon.bind('<Enter>', on_enter)
            more_icon.bind('<Leave>', on_leave)
            more_icon.bind('<Button-1>', lambda e, msg=m: self.show_message_menu(e, msg))
            content_text = tk.Text(frame, font=('Segoe UI', 10), fg='#dcddde', bg=frame_bg, wrap='word', relief='flat', borderwidth=0, highlightthickness=0, height=1)
            content_text.insert('1.0', m['content'])
            content_text.config(state='disabled')
            lines = m['content'].count('\n') + 1
            width = 80
            import textwrap
            wrapped = textwrap.wrap(m['content'], width=width)
            nlines = max(len(wrapped), lines)
            content_text.config(height=nlines)
            content_text.pack(anchor='w', fill='x', padx=0, pady=0)
            if m.get('attachments'):
                for att in m['attachments']:
                    if att.get('url', '').lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        self._add_image_to_frame(frame, att['url'])
            for emb in m.get('embeds', []):
                if emb.get('image_url'):
                    self._add_image_to_frame(frame, emb['image_url'])
            for emb in m.get('embeds', []):
                emb_frame = tk.Frame(frame, bg='#23272a', padx=8, pady=4)
                emb_frame.pack(anchor='w', fill='x', pady=4)
                if emb.get('title'):
                    tk.Label(emb_frame, text=emb['title'], font=('Segoe UI', 10, 'bold'), fg='#57f287', bg='#23272a', anchor='w').pack(anchor='w')
                if emb.get('description'):
                    tk.Label(emb_frame, text=emb['description'], font=('Segoe UI', 10), fg='#dcddde', bg='#23272a', anchor='w', wraplength=650, justify='left').pack(anchor='w')
                if emb.get('url'):
                    tk.Label(emb_frame, text=emb['url'], font=('Segoe UI', 9, 'underline'), fg='#00b0f4', bg='#23272a', anchor='w', cursor='hand2').pack(anchor='w')
            if idx < len(self.messages) - 1:
                hr = tk.Frame(self.messages_frame, bg='#202225', height=1)
                hr.pack(fill='x', padx=0, pady=6)
        self.messages_frame.update_idletasks()
        self.chat_canvas.config(scrollregion=self.chat_canvas.bbox('all'))
    def show_message_menu(self, event, msg):
        menu = tk.Menu(self.root, tearoff=0, bg='#23272a', fg='white', activebackground='#5865f2', activeforeground='white')
        menu.add_command(label='Скопировать Discord ID сообщения', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(str(msg['id']))))
        menu.add_command(label='Скопировать ссылку на сообщение', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(self.get_message_url(msg))))
        menu.add_command(label='Скопировать Discord ID пользователя', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(str(msg['author_id']))))
        menu.add_command(label='Скопировать текст сообщения', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(msg['content'])))
        menu.tk_popup(event.x_root, event.y_root)
    def get_message_url(self, msg):
        if not self.selected_guild or not self.selected_channel:
            return ''
        return f'https://discord.com/channels/{self.selected_guild.id}/{self.selected_channel.id}/{msg["id"]}'

    def send_message(self):
        content = self.message_entry.get().strip()
        if not content or not self.selected_channel:
            return
        asyncio.run_coroutine_threadsafe(self.selected_channel.send(content), self.loop)
        self.message_entry.delete(0, 'end')

    def _add_image_to_frame(self, frame, url):
        try:
            import requests
            from PIL import Image, ImageTk
            import io
            response = requests.get(url)
            img_data = response.content
            image = Image.open(io.BytesIO(img_data))
            image.thumbnail((350, 350))
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(frame, image=photo, bg=frame['bg'])
            label.image = photo
            label.pack(anchor='w', pady=4)
        except Exception:
            pass

def start_gui():
    def on_auth(token):
        auth_win.root.destroy()
        gui = MainGUI(token)
        gui.root.mainloop()
    root = tk.Tk()
    auth_win = AuthWindow(root, on_auth)
    root.mainloop()

if __name__ == '__main__':
    start_gui() 