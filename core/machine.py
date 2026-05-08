"""
machine.py  ─  Thermal Testing Machine Communication Layer

封包格式（528 bytes）：
  buf[0~3]   = CRC / Header (Little-Endian uint32)
  buf[4]     = 0x52 (CMD_READ 'R') / 0x57 (CMD_WRITE 'W')
  buf[5]     = 0x44 (CMD_READ 'D') / 0x52 (CMD_WRITE 'R')
  buf[6~7]   = 讀寫長度 (Little-Endian, READ 用 0x00FB)
  buf[8~11]  = 起始位址 (Little-Endian, 一般為 0x00000000)
  buf[12~]   = 資料區（RAM dump 從此開始，RAM address 0x00 對應 buf[12]）

★ buf 索引換算：buf_index = RAM_address + 12
  因為封包 header 佔 buf[0~11] 共 12 bytes，
  讀 RAM address 0xXX 時，實際應讀 buf[0xXX + 0x0C]。

關鍵 RAM 位址對照（原廠 DOC，Little-Endian）：
  RAM addr   型別       說明
  ─────────  ─────────  ─────────────────────────────────
  0x00       int32      RunSetting  控制位元
  0x08       int32      IO Output   輸出控制
  0x0C       int32      IO Input    輸入狀態
  0x70~0x84  float32×6  Temp CH1~6  單位：°C
  0xA0~0xB4  int32×6    LVDT CH1~6  單位：AD值 → 需換算 mm
  0xB8       float32    LVDT_Rate   無作用
  0xBC       float32    LVDT_Capacity 無作用

對應的 buf 索引（= RAM addr + 0x0C）：
  RAM 0x00 → buf[0x0C]    RAM 0x08 → buf[0x14]
  RAM 0x70 → buf[0x7C]    RAM 0xA0 → buf[0xAC]（LVDT CH1）
"""

import socket
import threading
import time
import struct
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal


# ─────────────────────────────────────────────────────────
#  協議常數
# ─────────────────────────────────────────────────────────
PACKET_SIZE   = 528
CMD_READ      = (0x52, 0x44)
CMD_WRITE     = (0x57, 0x52)

# ── 所有 buf 索引 = RAM address + 0x0C（header 12 bytes 偏移）
# 原廠 DOC 記載的是 RAM address；struct.unpack_from 讀的是 buf 索引。
#
# Temp：RAM 0x70~0x84  →  buf [0x7C, 0x80, 0x84, 0x88, 0x8C, 0x90]
OFFSET_TEMP   = [0x7C, 0x80, 0x84, 0x88, 0x8C, 0x90]

# LVDT：RAM 0xA0~0xB4  →  buf [0xAC, 0xB0, 0xB4, 0xB8, 0xBC, 0xC0]
# （DOC：Test LVDT1=0xA0, LVDT2=0xA4 ... LVDT6=0xB4，全部 +0x0C）
OFFSET_LVDT   = [0xAC, 0xB0, 0xB4, 0xB8, 0xBC, 0xC0]

# 控制位元：RAM 0x00, 0x08, 0x0C  →  buf 0x0C, 0x14, 0x18
OFFSET_RUN    = 0x0C   # RAM 0x00  RunSetting
OFFSET_IO_OUT = 0x14   # RAM 0x08  IO Output
OFFSET_IO_IN  = 0x18   # RAM 0x0C  IO Input

# 實測換算係數：(移動 -4.245mm) / (delta AD 29169) ≈ -0.0001455 mm/AD
# 負號：AD 增大 → 行程為負（棒子往內縮）
# 待校正：接上其餘插槽後，用 machine.calibrate() 確認係數
LVDT_AD_TO_MM: float = +0.000867


# ─────────────────────────────────────────────────────────
#  CRC 計算（
# ─────────────────────────────────────────────────────────
def _calc_crc(buf: bytearray) -> bytes:
    num = 0
    cmd = (buf[4], buf[5])
    if cmd == CMD_READ:
        for i in range(4, 12, 4):
            num += buf[i] + buf[i+1]*256 + buf[i+2]*65536 + buf[i+3]*16777216
    elif cmd == CMD_WRITE:
        for i in range(4, 12, 4):
            num += buf[i] + buf[i+1]*256 + buf[i+2]*65536 + buf[i+3]*16777216
        n_bytes = buf[6] + buf[7] * 256
        j, r, idx = n_bytes // 4, n_bytes % 4, 12
        for _ in range(j):
            num += buf[idx] + buf[idx+1]*256 + buf[idx+2]*65536 + buf[idx+3]*16777216
            idx += 4
        if r >= 1: num += buf[idx]
        if r >= 2: num += buf[idx+1] * 256
        if r >= 3: num += buf[idx+2] * 65536
    return struct.pack('<I', num & 0xFFFFFFFF)


def _build_read_packet() -> bytes:
    """建立標準讀取封包（與Reference software Wireshark 抓包格式完全一致）

    Wireshark 確認：Reference software送出的 TCP payload 開頭為：
        52 44 fb 00  52 44 fb 00  00 00 00 00 ...
    buf[0~3] = 52 44 fb 00（固定 header，非計算 CRC）
    buf[4~5] = 52 44（CMD_READ）
    buf[6~7] = fb 00（讀取長度 0x00FB）
    """
    buf = bytearray(PACKET_SIZE)
    buf[0], buf[1], buf[2], buf[3] = 0x52, 0x44, 0xFB, 0x00  # 固定 header
    buf[4], buf[5] = 0x52, 0x44                                # CMD_READ
    buf[6], buf[7] = 0xFB, 0x00                                # 讀取長度
    return bytes(buf)


READ_PACKET = _build_read_packet()   # 預建立，避免重複計算


# ─────────────────────────────────────────────────────────
#  資料類別
# ─────────────────────────────────────────────────────────
class ChannelData:
    def __init__(self, ch_id: int):
        self.ch_id            = ch_id
        self.temperature      = 0.0
        self.deflection       = 0.0      # 換算後 mm（已減去歸零基準）
        self.raw_ad           = 0        # 原始 AD 值
        self.zero_ref_ad      = None     # 軟體歸零時記錄的 AD 基準值
        self.enabled          = True
        self.test_method      = "HDT-ASTM"
        self.weight_g         = 0.0
        self.deflection_limit = 0.25   # mm


class TestingMachine(QObject):
    data_updated      = pyqtSignal(list)
    status_updated    = pyqtSignal(str)
    connected         = pyqtSignal(bool)
    raw_data_received = pyqtSignal(bytes)

    def __init__(self, host="192.168.1.100", port=1500, simulation=False):
        super().__init__()
        self.host       = host
        self.port       = port
        self.simulation = simulation
        self.sock: Optional[socket.socket] = None
        self.running    = False
        self.channels: List[ChannelData] = [ChannelData(i + 1) for i in range(6)]
        self._lock      = threading.Lock()
        self._last_packet: Optional[bytes] = None
        self._packet_count = 0

        self.test_running    = False
        self.test_start_time: Optional[float] = None
        self.heating_rate    = 50.0

        # 除錯：印前 N 個封包（設 0 關閉）
        self._debug_packets = 3

    # ──────────────────────────────────────────────────────
    #  連線
    # ──────────────────────────────────────────────────────
    def connect(self) -> bool:
        if self.simulation:
            return self._start_simulation()

        self.status_updated.emit(f"正在連線 {self.host}:{self.port} ...")
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(2.0)
            #print(f"[CONNECT] 連上 {self.host}:{self.port}")

            self.connected.emit(True)
            self.running = True
            self.status_updated.emit(f"✅ 連線成功  {self.host}:{self.port}")
            threading.Thread(target=self._receive_loop, daemon=True).start()
            return True

        except Exception as e:
            self.status_updated.emit(f"❌ 連線失敗: {e}")
            self.connected.emit(False)
            return False

    def disconnect(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # ──────────────────────────────────────────────────────
    #  安全 emit（視窗關閉後 Qt 物件已銷毀時靜默忽略）
    # ──────────────────────────────────────────────────────
    def _safe_emit_status(self, msg: str):
        try:
            self.status_updated.emit(msg)
        except RuntimeError:
            pass

    def _safe_emit_data(self, channels: list):
        try:
            self.data_updated.emit(channels)
        except RuntimeError:
            pass

    def _safe_emit_connected(self, ok: bool):
        try:
            self.connected.emit(ok)
        except RuntimeError:
            pass

    # ──────────────────────────────────────────────────────
    #  接收迴圈（問答模式：送 READ 封包 → 收 528 byte 回應）
    # ──────────────────────────────────────────────────────
    def _receive_loop(self):
        while self.running:
            try:
                # 送讀取指令
                with self._lock:
                    self.sock.sendall(READ_PACKET)

                # 收完整 528 bytes 回應
                data = self._recv_exact(PACKET_SIZE)
                if data is None:
                    if self.running:
                        print("[DISCONNECT] 未收到完整封包")
                        self._safe_emit_status("⚠️ 連線中斷")
                        self._safe_emit_connected(False)
                    break

                self._process_packet(data)

            except socket.timeout:
                #print("[TIMEOUT] 重試")
                continue
            except RuntimeError:
                # Qt 物件已銷毀（視窗關閉），直接結束 thread
                self.running = False
                break
            except Exception as e:
                if self.running:
                    #print(f"[RECV ERR] {e}")
                    self._safe_emit_status(f"⚠️ 接收錯誤: {e}")
                time.sleep(0.1)

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """確保收到剛好 n bytes"""
        buf = b""
        while len(buf) < n and self.running:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except socket.timeout:
                continue
            except Exception:
                return None
        return buf if len(buf) == n else None

    def _process_packet(self, packet: bytes):
        self._packet_count += 1
        self._last_packet = packet
        try:
            self.raw_data_received.emit(packet)
        except RuntimeError:
            return

        # ── 除錯輸出（前 N 封包）
        if self._packet_count <= self._debug_packets:
            for i, off in enumerate(OFFSET_LVDT):
                ad = struct.unpack_from('<i', packet, off)[0]
                ref = self.channels[i].zero_ref_ad or ad
            for i, off in enumerate(OFFSET_TEMP):
                t = struct.unpack_from('<f', packet, off)[0]
                #print(f"  TEMP CH{i+1} = {t:.2f} °C")

        # ── 解析 LVDT（每個通道讀自己的 offset，軟體歸零）
        for i, off in enumerate(OFFSET_LVDT):
            if off + 4 <= len(packet):
                ad = struct.unpack_from('<i', packet, off)[0]
                ch = self.channels[i]
                ch.raw_ad = ad
                # 第一包自動設定歸零基準（尚未手動歸零時）
                if ch.zero_ref_ad is None:
                    ch.zero_ref_ad = ad
                ch.deflection = (ad - ch.zero_ref_ad) * LVDT_AD_TO_MM

        # ── 解析溫度
        for i, off in enumerate(OFFSET_TEMP):
            if off + 4 <= len(packet):
                t = struct.unpack_from('<f', packet, off)[0]
                if -50.0 < t < 400.0:
                    self.channels[i].temperature = t

        self._safe_emit_data(self.channels)

    # ──────────────────────────────────────────────────────
    #  模擬模式
    # ──────────────────────────────────────────────────────
    def _start_simulation(self):
        self.connected.emit(True)
        self.running = True
        self.status_updated.emit("🔧 模擬模式啟動")
        threading.Thread(target=self._simulation_loop, daemon=True).start()
        return True

    def _simulation_loop(self):
        import math, random
        t = 0
        while self.running:
            time.sleep(0.1)
            t += 0.1
            for i, ch in enumerate(self.channels):
                phase = i * (math.pi / 3)
                if self.test_running:
                    ch.temperature = min(300.0, ch.temperature + self.heating_rate / 36000)
                    ch.deflection  = max(-9.0,
                        -abs(math.sin(t * 0.3 + phase)) * 5 - random.uniform(0, 0.02))
                else:
                    ch.temperature = 25.0 + math.sin(t * 0.05 + phase) * 0.5
                    ch.deflection  = math.sin(t * 0.8 + phase) * 0.05
            self.data_updated.emit(self.channels)

    # ──────────────────────────────────────────────────────
    #  控制指令
    # ──────────────────────────────────────────────────────
    def move_up(self):
        self._write_io(self._io_with_bit(2, True))

    def move_down(self):
        self._write_io(self._io_with_bit(3, True))

    def stop(self):
        cur = self._cur_io_out()
        cur &= ~(1 << 2)
        cur &= ~(1 << 3)
        self._write_io(cur)

    def zero(self):
        """LVDT 軟體歸零：以目前的 AD 原始值為基準點，後續顯示差值。
        
        確認：Reference software按 ZERO 時也只是軟體記錄基準，不送 WRITE 指令。
        Wireshark 抓包顯示Reference software全程只送讀取封包。
        """
        for ch in self.channels:
            ch.zero_ref_ad = ch.raw_ad   # 記住當前 AD 為基準
            ch.deflection = 0.0
        self.data_updated.emit(self.channels)
        self.status_updated.emit("◎ LVDT 歸零（軟體基準已更新）")

    def start_test(self):
        self.test_running    = True
        self.test_start_time = time.time()
        # _write_run 已移除：Wireshark 確認機台不接受 WRITE 指令，
        # 送出後機台不回 ACK → timeout → connection fail
        self._safe_emit_status("▶ 測試開始")

    def stop_test(self):
        self.test_running = False
        self._safe_emit_status("⏹ 測試停止")

    def _cur_run(self) -> int:
        p = self._last_packet
        return struct.unpack_from('<I', p, OFFSET_RUN)[0] if p else 0

    def _cur_io_out(self) -> int:
        p = self._last_packet
        return struct.unpack_from('<I', p, OFFSET_IO_OUT)[0] if p else 0

    def _io_with_bit(self, bit: int, on: bool) -> int:
        cur = self._cur_io_out()
        return (cur | (1 << bit)) if on else (cur & ~(1 << bit))

    def _write_run(self, value: int):
        self._raw_write(OFFSET_RUN, value)

    def _write_io(self, value: int):
        self._raw_write(OFFSET_IO_OUT, value)

    def _raw_write(self, addr: int, value: int):
        """寫入封包：CMD_WRITE + addr + 4 bytes data"""
        if not self.sock or self.simulation:
            return
        try:
            buf = bytearray(PACKET_SIZE)
            buf[4], buf[5] = CMD_WRITE          # 0x57, 0x52
            buf[6], buf[7] = 0x04, 0x00         # 寫 4 bytes
            buf[8]  = addr & 0xFF               # 位址 (Little-Endian)
            buf[9]  = (addr >> 8) & 0xFF
            buf[10] = (addr >> 16) & 0xFF
            buf[11] = (addr >> 24) & 0xFF
            struct.pack_into('<I', buf, 12, value)   # 資料

            # 補零 padding
            n_bytes = 4
            r = n_bytes % 4
            if r != 0:
                base = 12 + (n_bytes // 4) * 4 + r
                for k in range(4 - r):
                    if base + k < PACKET_SIZE:
                        buf[base + k] = 0

            crc = _calc_crc(buf)
            buf[0], buf[1], buf[2], buf[3] = crc[0], crc[1], crc[2], crc[3]

            with self._lock:
                self.sock.sendall(bytes(buf))
                # 等待 ACK：回應封包的 buf[8]/buf[9] 要與送出的相同
                ack = self._recv_exact(PACKET_SIZE)
                if ack and ack[8] == buf[8] and ack[9] == buf[9]:
                    self.status_updated.emit(f"→ W 0x{addr:02X}={value:08X} ✓")
                else:
                    self.status_updated.emit(f"→ W 0x{addr:02X} (no ACK)")

        except Exception as e:
            self.status_updated.emit(f"寫入失敗: {e}")

    # ──────────────────────────────────────────────────────
    #  除錯 / 校正
    # ──────────────────────────────────────────────────────
    def dump(self):
        """印出最新封包所有關鍵欄位"""
        p = self._last_packet
        if not p:
            #print("[DUMP] 尚未收到封包")
            return
        #print(f"封包長度: {len(p)}")
        #print(f"RunSetting 0x00 : {self._cur_run():032b}")
        #print(f"IO Output  0x08 : {self._cur_io_out():08b}")
        #print(f"IO Input   0x0C : {struct.unpack_from('<I', p, 0x0C)[0]:08b}")
        for i, off in enumerate(OFFSET_LVDT):
            ad = struct.unpack_from('<i', p, off)[0]
            ref = self.channels[i].zero_ref_ad or ad
            #print(f"LVDT CH{i+1}  0x{off:02X}: AD={ad:10d}  ref={ref}  deflection={(ad-ref)*LVDT_AD_TO_MM:+.4f} mm")
        print()
        for i, off in enumerate(OFFSET_TEMP):
            t = struct.unpack_from('<f', p, off)[0]
            #print(f"TEMP CH{i+1}  0x{off:02X}: {t:.2f} °C")

    def calibrate(self, ch_index: int, known_mm: float):
        """
        單點校正 LVDT 換算係數。
        把棒子移到已知位置（known_mm），然後呼叫：
          machine.calibrate(5, 1.0)   # CH6，位移 1.0mm
        """
        global LVDT_AD_TO_MM
        p = self._last_packet
        if not p:
            #print("[CAL] 尚未收到封包")
            return
        ad = struct.unpack_from('<i', p, OFFSET_LVDT[ch_index])[0]
        zero_ref = self.channels[ch_index].zero_ref_ad or 0
        delta_ad = ad - zero_ref
        if delta_ad == 0:
            #print("[CAL] delta_AD=0，請先歸零再移動棒子到已知距離")
            return
        global LVDT_AD_TO_MM
        LVDT_AD_TO_MM = known_mm / delta_ad
        print(f"[CAL] AD={ad}  zero_ref={zero_ref}  delta={delta_ad}  "
              f"known={known_mm} mm  LVDT_AD_TO_MM={LVDT_AD_TO_MM:.8f}")