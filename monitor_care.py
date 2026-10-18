# -*- coding: utf-8 -*-
"""フローライト Eye モニター Info / v0.10.3
ローカル完結のWindows向けモニター目視診断ツール。
"""
import os, sys, json, platform, ctypes, subprocess
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# STEP 1: Windowsのタスクバーに別アプリとして認識させる設定
if sys.platform == "win32":
    try:
        myappid = "fluorite.eye.monitor.info.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

# STEP 2: exe化時の一時展開先から正しいパスを取得する関数
def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

APP_NAME = "フローライト Eye モニター Info"
APP_VERSION = "0.10.3"

PATTERNS = [
    ("黒", "#000000", "明るい点や光漏れを確認します。"),
    ("白", "#FFFFFF", "暗い点、色むら、明るさのむらを確認します。"),
    ("赤", "#FF0000", "赤サブピクセルの欠けや色の異常を確認します。"),
    ("緑", "#00FF00", "緑サブピクセルの欠けや色の異常を確認します。"),
    ("青", "#0000FF", "青サブピクセルの欠けや色の異常を確認します。"),
    ("グレー", "#808080", "輝度むら、色むら、残像を目視確認します。"),
    ("濃いグレー", "#202020", "暗部のむらや光漏れを確認します。"),
    ("グラデーション", "gradient", "階調の段差、縞、色の変化を確認します。"),
    ("カラーバー", "bars", "色の表示や色の異常を目視確認します。"),
    ("文字", "text", "文字のにじみ、ぼけ、表示位置を確認します。"),
]
CHECKS = [
    ("pixel", "ドット抜け・常時点灯", "単色の黒・白・赤・緑・青を表示して確認"),
    ("uniformity", "色むら・輝度むら", "白・グレー画面で画面全体を確認"),
    ("bleed", "光漏れ・暗部のむら", "黒・濃いグレー画面で確認"),
    ("afterimage", "焼き付き・残像の疑い", "グレー画面などで残像がないか確認"),
    ("color", "色表示・階調", "カラーバー・グラデーションで確認"),
    ("text", "文字のにじみ・表示", "文字テストで読みやすさを確認"),
]

def get_primary_display_metrics():
    """Windows標準APIから取得できる表示設定。"""
    result = {"取得方式": "Windows標準API", "取得状態": "未取得"}
    if sys.platform != "win32":
        result["取得状態"] = "Windows以外のため対象外"
        return result
    try:
        from ctypes import wintypes
        class DEVMODEW(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", wintypes.SHORT), ("dmDuplex", wintypes.SHORT),
                ("dmYResolution", wintypes.SHORT), ("dmTTOption", wintypes.SHORT),
                ("dmCollate", wintypes.SHORT), ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]
        dm = DEVMODEW(); dm.dmSize = ctypes.sizeof(DEVMODEW)
        ok = ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
        if ok:
            result.update({
                "取得状態": "取得成功",
                "解像度": f"{dm.dmPelsWidth} × {dm.dmPelsHeight}",
                "色深度": f"{dm.dmBitsPerPel} bit",
                "リフレッシュレート": f"{dm.dmDisplayFrequency} Hz" if dm.dmDisplayFrequency else "不明"
            })
        else:
            result["取得状態"] = "Windows APIから取得できませんでした"
    except Exception as e:
        result["取得状態"] = f"取得失敗: {e}"
    return result

def get_monitor_info():
    info = {"OS": platform.platform(), "PC名": platform.node(), "アプリ版": APP_VERSION, "表示設定チェック": get_primary_display_metrics()}
    pnp = {"取得状態": "取得不可", "モニター": []}
    if sys.platform == "win32":
        ps_script = r"""$ErrorActionPreference='SilentlyContinue'
$ids = @(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID | ForEach-Object {
  $name = -join ($_.UserFriendlyName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
  $maker = -join ($_.ManufacturerName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
  $serial = -join ($_.SerialNumberID | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
  $productCode = -join ($_.ProductCodeID | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
  $week = $null; if ($_.WeekOfManufacture -gt 0 -and $_.WeekOfManufacture -le 53) { $week = [int]$_.WeekOfManufacture }
  $year = $null; if ($_.YearOfManufacture -ge 1990 -and $_.YearOfManufacture -le 2100) { $year = [int]$_.YearOfManufacture }
  [PSCustomObject]@{ Active=$_.Active; InstanceName=$_.InstanceName; Manufacturer=$maker; ProductName=$name; SerialNumber=$serial; ProductCode=$productCode; YearOfManufacture=$year; WeekOfManufacture=$week }
})
[PSCustomObject]@{ MonitorIDs=$ids } | ConvertTo-Json -Depth 5 -Compress"""
        try:
            proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if proc.returncode == 0 and proc.stdout.strip():
                raw = json.loads(proc.stdout.strip())
                ids = raw.get("MonitorIDs", [])
                if isinstance(ids, dict): ids = [ids]
                pnp = {"取得状態": "取得成功", "モニター": ids}
        except Exception:
            pass
    info["PnPモニター情報"] = pnp
    return info

def get_display_monitors():
    if sys.platform != "win32":
        return [{"name": "メイン画面（自動検出）", "x": 0, "y": 0, "width": 0, "height": 0, "primary": True}]
    try:
        from ctypes import wintypes
        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]
        user32 = ctypes.windll.user32
        monitors = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
        def callback(hmonitor, hdc, rect_ptr, lparam):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                r = info.rcMonitor
                monitors.append({
                    "name": info.szDevice, "x": int(r.left), "y": int(r.top),
                    "width": int(r.right-r.left), "height": int(r.bottom-r.top),
                    "primary": bool(info.dwFlags & 1)
                })
            return True
        user32.EnumDisplayMonitors(0, 0, callback_type(callback), 0)
        monitors.sort(key=lambda m: (not m["primary"], m["x"], m["y"]))
        if monitors: return monitors
    except Exception:
        pass
    return [{"name": "メイン画面（自動検出）", "x": 0, "y": 0, "width": 0, "height": 0, "primary": True}]

class PatternWindow:
    def __init__(self, master, index, monitor=None):
        self.index = index
        self.monitor = monitor or get_display_monitors()[0]
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{self.monitor['width']}x{self.monitor['height']}+{self.monitor['x']}+{self.monitor['y']}")
        self.show_intro = True
        # キー操作はここで一元管理する。render_intro() 側で Space を再bindすると
        # 既存の切替処理が上書きされ、検査画面で Space が効かなくなるため。
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<Right>", lambda e: self.intro_or_move(1))
        self.win.bind("<Left>", lambda e: self.intro_or_move(-1))
        self.win.bind("<space>", self.on_space)
        self.win.bind("<Return>", self.on_enter)
        self.win.bind("<F11>", lambda e: self.toggle_help())
        self.win.after(100, self.activate_window)
        self.render_intro()

    def activate_window(self):
        # キー入力を受け取れるよう、全画面ウィンドウを前面にしてフォーカスする。
        try:
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def on_space(self, event=None):
        if self.show_intro:
            self.start_pattern()
        else:
            self.move(1)
        return "break"

    def on_enter(self, event=None):
        if self.show_intro:
            self.start_pattern()
        return "break"

    def intro_or_move(self, delta):
        if self.show_intro:
            self.index = (self.index + delta) % len(PATTERNS)
            self.render_intro()
        else:
            self.move(delta)

    def move(self, delta):
        if self.show_intro:
            self.show_intro = False
            self.render()
            return
        self.index = (self.index + delta) % len(PATTERNS)
        self.render()

    def render_intro(self):
        for w in self.win.winfo_children(): w.destroy()
        self.win.configure(bg="#111827")
        name, color, desc = PATTERNS[self.index]
        frame = tk.Frame(self.win, bg="#111827")
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text=f"目視確認 {self.index + 1}", bg="#111827", fg="#FFFFFF", font=("Segoe UI", 30, "bold")).pack(pady=(0, 12))
        tk.Label(frame, text=name, bg="#111827", fg="#FFFFFF", font=("Segoe UI", 24, "bold")).pack(pady=8)
        tk.Label(frame, text=desc, bg="#111827", fg="#E5E7EB", font=("Segoe UI", 16), wraplength=1000, justify="center").pack(pady=12)
        tk.Label(frame, text="クリック または Enter / Space で検査画面を表示", bg="#111827", fg="#FDE68A", font=("Segoe UI", 16, "bold")).pack(pady=18)
        tk.Label(frame, text="← → キー：検査項目を変更 ｜ Esc：終了 ｜ F11：案内表示の切替", bg="#111827", fg="#D1D5DB", font=("Segoe UI", 12)).pack(pady=8)
        # クリックで開始。Enter / Space のキー処理は __init__ のbindを使う。
        self.win.bind("<Button-1>", lambda e: self.start_pattern())
        self.top = None
        self.bottom = None

    def start_pattern(self):
        if self.show_intro:
            self.show_intro = False
            self.render()

    def render(self):
        for w in self.win.winfo_children(): w.destroy()
        name, color, desc = PATTERNS[self.index]
        if color in ("gradient", "bars"):
            canvas = tk.Canvas(self.win, highlightthickness=0, bg="black")
            canvas.pack(fill="both", expand=True)
            self.win.update_idletasks()
            width, height = max(1, self.win.winfo_width()), max(1, self.win.winfo_height())
            if color == "gradient":
                steps = min(width, 512)
                for i in range(steps):
                    v = int(i*255/max(steps-1,1)); c=f"#{v:02x}{v:02x}{v:02x}"
                    canvas.create_rectangle(i*width/steps,0,(i+1)*width/steps+1,height,fill=c,outline=c)
            else:
                colors=["#FFFFFF","#FFFF00","#00FFFF","#00FF00","#FF00FF","#FF0000","#0000FF","#000000"]
                for i,c in enumerate(colors):
                    canvas.create_rectangle(i*width/len(colors),0,(i+1)*width/len(colors)+1,height,fill=c,outline=c)
        elif color == "text":
            self.win.configure(bg="#808080")
            tk.Label(self.win, text="ABCDEFGHJKLMNPQRSTUVWXYZ\nabcdefghijkmnopqrstuvwxyz\n0123456789\nあいうえお カキクケコ 漢字",
                     bg="#808080", fg="#000000", font=("Segoe UI", 34)).pack(expand=True)
        else:
            self.win.configure(bg=color)
        self.top = tk.Label(self.win, text=f"目視確認 {self.index + 1}：{name} | ← → / Space: 切替 | Esc: 終了 | F11: 説明", bg="#222222", fg="white", font=("Segoe UI",12), padx=12,pady=8)
        self.top.place(relx=.5,rely=.02,anchor="n")
        self.bottom = tk.Label(self.win,text=desc,bg="#222222",fg="white",font=("Segoe UI",12),padx=12,pady=8)
        self.bottom.place(relx=.5,rely=.98,anchor="s")

    def toggle_help(self):
        if self.top.winfo_viewable():
            self.top.place_forget(); self.bottom.place_forget()
        else:
            self.top.place(relx=.5,rely=.02,anchor="n"); self.bottom.place(relx=.5,rely=.98,anchor="s")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1100x800"); self.minsize(900,700)

        # 蛍石アイコンの設定（タイトルバー・タスクバー両方に対応）
        try:
            icon_path = get_resource_path("fluorite_eye_icon.ico")
            if os.path.exists(icon_path):
                try:
                    # iconphotoを使うことでタイトルバーとタスクバー両方に反映されやすくなります
                    icon_img = tk.PhotoImage(file=icon_path)
                    self.iconphoto(True, icon_img)
                except Exception:
                    self.iconbitmap(default=icon_path)
        except Exception as e:
            print(f"アイコンの設定に失敗しました: {e}")

        self.info = get_monitor_info()
        self.build_ui()
        self.refresh_info()

    def build_ui(self):
        header = ttk.Frame(self, padding=(16, 12))
        header.pack(fill="x")
        title_row = ttk.Frame(header)
        title_row.pack(fill="x", anchor="w")
        ttk.Label(title_row, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(
            title_row,
            text="Windows版",
            font=("Segoe UI", 20, "bold"),
            foreground="#174A82",
            padding=(14, 2),
        ).pack(side="left", padx=(18, 0))
        ttk.Label(
            header,
            text="ローカル完結型 モニター目視診断ツール",
            foreground="#555",
        ).pack(anchor="w", pady=(5, 0))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.home = ttk.Frame(self.nb, padding=16)
        self.test = ttk.Frame(self.nb, padding=16)

        self.nb.add(self.home, text="① ホーム")
        self.nb.add(self.test, text="② 診断・判定")

        self.build_home()
        self.build_test()

    def build_home(self):
        ttk.Label(self.home, text="PC・接続モニター情報", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(self.home, text="PCの基本情報、各モニターのメーカー・型番・製造年月・シリアル番号、解像度・色深度・リフレッシュレートを確認できます。", foreground="#555", wraplength=950).pack(anchor="w", pady=4)

        controls = ttk.Frame(self.home)
        controls.pack(fill="x", pady=8)
        ttk.Button(controls, text="情報を再取得", command=self.refresh_info).pack(side="left")

        self.monitor_summary = ttk.Label(self.home, text="モニター情報を読み込み中…", font=("Segoe UI", 11, "bold"))
        self.monitor_summary.pack(anchor="w", pady=(0, 6))

        columns = ("item", "value", "status")
        self.monitor_tree = ttk.Treeview(self.home, columns=columns, show="headings", height=16)
        self.monitor_tree.heading("item", text="項目")
        self.monitor_tree.heading("value", text="取得値")
        self.monitor_tree.heading("status", text="取得状況・補足")
        self.monitor_tree.column("item", width=200, minwidth=150, anchor="w")
        self.monitor_tree.column("value", width=320, minwidth=200, anchor="w")
        self.monitor_tree.column("status", width=430, minwidth=250, anchor="w")
        self.monitor_tree.pack(fill="both", expand=True, pady=4)
        self.monitor_tree.tag_configure("section", background="#D9EAF7", font=("Segoe UI", 10, "bold"))
        self.monitor_tree.tag_configure("missing", foreground="#8A4B08")

        note = tk.Label(self.home, text="※ PC・モニター情報は画面上で確認できます。", justify="left", anchor="w", wraplength=950, fg="#555555", font=("Segoe UI", 9))
        note.pack(fill="x", pady=(8, 0))

    def refresh_info(self):
        self.info = get_monitor_info()
        if not hasattr(self, "monitor_tree"): return
        for item in self.monitor_tree.get_children(): self.monitor_tree.delete(item)
        pnp = self.info.get("PnPモニター情報", {})
        monitors = pnp.get("モニター", []) if isinstance(pnp, dict) else []
        if isinstance(monitors, dict): monitors = [monitors]
        
        display = self.info.get("表示設定チェック", {})
        primary_display_str = f"解像度: {display.get('解像度', '不明')} | 色深度: {display.get('色深度', '不明')} | リフレッシュレート: {display.get('リフレッシュレート', '不明')}"
        self.monitor_summary.configure(text=f"検出モニター数: {len(monitors)} 台  |  プライマリ表示: {primary_display_str}")

        def add(section, rows):
            self.monitor_tree.insert("", "end", values=(section, "", ""), tags=("section",))
            for label, value, status in rows:
                self.monitor_tree.insert("", "end", values=(label, value, status), tags=(("missing",) if value in ("不明", "取得不可", "未登録") else ()))

        for i, m in enumerate(monitors, 1):
            maker = str(m.get("Manufacturer", "")).strip() or "不明"
            model = str(m.get("ProductName", "")).strip() or "Generic Monitor / 未登録"
            add(f"モニター {i}：{maker}  {model}", [
                ("メーカー", maker, "EDID / WMI"),
                ("機種名", model, "EDIDの製品名"),
                ("製造年", f"{m.get('YearOfManufacture')}年" if m.get("YearOfManufacture") else "不明", "EDIDの製造年"),
                ("製造週", f"第{m.get('WeekOfManufacture')}週" if m.get("WeekOfManufacture") else "不明", "EDIDの製造週"),
                ("シリアル番号", str(m.get("SerialNumber", "")).strip() or "未登録", "EDID / WMI"),
                ("製品コード", str(m.get("ProductCode", "")).strip() or "未登録", "EDID / WMI"),
                ("接続状態", "接続中" if m.get("Active") is True else "不明", str(m.get("InstanceName", ""))),
            ])
        if not monitors:
            add("モニター識別情報", [("取得状態", pnp.get("取得状態", "取得不可"), "Windowsのroot\\WMIから情報を取得できませんでした")])
        
        add("PC基本情報・プライマリ表示設定", [
            ("OS", self.info.get("OS", "不明"), "プラットフォーム情報"),
            ("PC名", self.info.get("PC名", "不明"), "ホスト名"),
            ("プライマリ解像度", display.get("解像度", "不明"), "Windows標準API"),
            ("色深度", display.get("色深度", "不明"), "Windows標準API"),
            ("リフレッシュレート", display.get("リフレッシュレート", "不明"), "Windows標準API"),
        ])

    def build_test(self):
        ttk.Label(self.test, text="診断テスト（目視チェック）", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(self.test, text="①検査対象モニターを選択 → ②全画面で検査パターンを表示 → ③正常例・異常例のサンプルと見比べて目視確認します。", wraplength=1200).pack(anchor="w", pady=5)
        
        monitor_frame = ttk.LabelFrame(self.test, text="検査対象モニターの選択", padding=8)
        monitor_frame.pack(fill="x", pady=5)
        self.available_monitors = get_display_monitors()
        monitor_labels = []
        for i, mon in enumerate(self.available_monitors, 1):
            primary_text = "（メイン）" if mon.get("primary") else ""
            resolution = f"{mon['width']}×{mon['height']}" if mon["width"] else "解像度自動"
            monitor_labels.append(f"モニター{i} — {mon['name']} {resolution}{primary_text}")
        self.monitor_list = ttk.Combobox(monitor_frame, state="readonly", values=monitor_labels, width=80)
        primary_index = next((i for i,m in enumerate(self.available_monitors) if m.get("primary")), 0)
        self.monitor_list.current(primary_index)
        self.monitor_list.pack(side="left", fill="x", expand=True, padx=(0,8))
        ttk.Button(monitor_frame, text="再取得", command=self.refresh_monitor_choices).pack(side="left")

        pattern_frame = ttk.LabelFrame(self.test, text="全画面での検査パターン表示（検査開始前の案内画面付き）", padding=8)
        pattern_frame.pack(fill="x", pady=5)
        self.pattern_list = ttk.Combobox(pattern_frame, state="readonly", values=[f"{n} — {d}" for n,c,d in PATTERNS], width=80)
        self.pattern_list.current(0)
        self.pattern_list.pack(side="left", fill="x", expand=True, padx=(0,8))
        ttk.Button(pattern_frame, text="全画面診断", command=self.launch_pattern).pack(side="left")

        check_frame = ttk.LabelFrame(self.test, text="既存の6種類の目視検査（正常例と異常例の比較）", padding=8)
        check_frame.pack(fill="both", expand=True, pady=7)
        headers = [("検査項目", 0), ("確認の目安", 1), ("正常な例", 2), ("異常がある例（赤丸が注目箇所）", 3)]
        for title, col in headers:
            ttk.Label(check_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, sticky="w", padx=5, pady=5)
        check_frame.grid_columnconfigure(1, weight=1)
        
        for row, (key, label, helptext) in enumerate(CHECKS, 1):
            ttk.Label(check_frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=6)
            ttk.Label(check_frame, text=helptext, wraplength=280).grid(row=row, column=1, sticky="w", padx=5, pady=6)
            
            normal = tk.Canvas(check_frame, width=190, height=56, highlightthickness=1, highlightbackground="#b7b7b7", bg="white")
            abnormal = tk.Canvas(check_frame, width=190, height=56, highlightthickness=1, highlightbackground="#b7b7b7", bg="white")
            normal.grid(row=row, column=2, padx=5, pady=4, sticky="w")
            abnormal.grid(row=row, column=3, padx=5, pady=4, sticky="w")
            self.draw_sample(normal, key, False)
            self.draw_sample(abnormal, key, True)


        ttk.Label(self.test, text="※ キーボード操作：← →キーでパターン切替、Spaceで検査開始、F11で説明切替、Escで終了します。", wraplength=1200, foreground="#555").pack(anchor="w")

    @staticmethod
    def draw_sample(canvas, key, abnormal):
        canvas.delete("all")
        w, h = 190, 56
        red = "#ff2020"
        if key == "pixel":
            canvas.create_rectangle(1,1,w-1,h-1,fill="#050505",outline="")
            if abnormal:
                canvas.create_oval(120,18,139,37,outline=red,width=2)
                canvas.create_rectangle(128,26,131,29,fill="#ffffff",outline="#ffffff")
        elif key == "uniformity":
            canvas.create_rectangle(1,1,w-1,h-1,fill="#999999",outline="")
            if abnormal:
                canvas.create_oval(100,5,180,51,fill="#686868",outline="")
                canvas.create_oval(100,5,180,51,outline=red,width=2)
        elif key == "bleed":
            canvas.create_rectangle(1,1,w-1,h-1,fill="#030303",outline="")
            if abnormal:
                canvas.create_polygon(1,1,70,1,48,12,27,27,1,38,fill="#665f4e",outline="")
                canvas.create_polygon(1,1,70,1,48,12,27,27,1,38,fill="",outline=red,width=2)
        elif key == "afterimage":
            canvas.create_rectangle(1,1,w-1,h-1,fill="#555555",outline="")
            if abnormal:
                canvas.create_rectangle(50,12,130,44,outline="#999999",width=2)
                canvas.create_rectangle(46,8,134,48,outline=red,width=2)
        elif key == "color":
            colors=["#ffffff","#ffff00","#00ffff","#00ff00","#ff00ff","#ff0000","#0000ff"]
            if abnormal: colors=["#ffffff","#ffff00","#00ffff","#00ff00","#00ff00","#ff0000","#0000ff"]
            x0, y0, bar_h = 2, 10, 20
            seg=(w-4)/len(colors)
            for i,c in enumerate(colors):
                canvas.create_rectangle(x0+i*seg,y0,x0+(i+1)*seg,y0+bar_h,fill=c,outline=c)
            if abnormal:
                canvas.create_oval(x0+3*seg-2,y0-2,x0+5*seg+2,y0+bar_h+2,outline=red,width=2)
        elif key == "text":
            canvas.create_rectangle(1,1,w-1,h-1,fill="#eeeeee",outline="")
            if abnormal:
                canvas.create_text(95,28,text="Aa あ漢",font=("Arial",16,"bold"),fill="#222222")
                canvas.create_rectangle(50,8,140,48,outline=red,width=2)
            else:
                canvas.create_text(95,28,text="Aa あ漢",font=("Arial",16,"bold"),fill="#111111")
        canvas.create_rectangle(1,1,w-1,h-1,outline="#888888")

    def refresh_monitor_choices(self):
        self.available_monitors = get_display_monitors()
        labels = []
        for i, mon in enumerate(self.available_monitors, 1):
            primary_text = "（メイン）" if mon.get("primary") else ""
            resolution = f"{mon['width']}×{mon['height']}" if mon["width"] else "解像度自動"
            labels.append(f"モニター{i} — {mon['name']} {resolution}{primary_text}")
        self.monitor_list.configure(values=labels)
        primary_index = next((i for i,m in enumerate(self.available_monitors) if m.get("primary")), 0)
        self.monitor_list.current(primary_index)
        messagebox.showinfo("モニター情報", f"{len(labels)}台のモニターを検出しました。")

    def launch_pattern(self):
        i = self.pattern_list.current()
        mi = self.monitor_list.current()
        if mi < 0 or mi >= len(self.available_monitors): mi = 0
        PatternWindow(self, i if i>=0 else 0, self.available_monitors[mi])


if __name__ == "__main__":
    try: App().mainloop()
    except Exception as exc:
        try: messagebox.showerror("起動エラー", f"アプリの起動に失敗しました。\n{exc}")
        except Exception: print(exc)