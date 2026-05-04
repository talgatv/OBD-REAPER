#!/usr/bin/env python3
import curses
import os
import datetime
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.elm327 import ELM327, ELMConnectionError
from core.scanner import Scanner, FINGERPRINT_ADDRS, ECU_NAMES
from core.reporter import Reporter, MODE_TOTALS
from plugins import load_plugins
from ui.banner import show_banner
from core import dtc_db as _dtc_db

C_GREEN = 1
C_WARN  = 2
C_ERR   = 3

MENU_ITEMS = [
    ("1", "QUICK SCAN",      "DTCs + status"),
    ("2", "FULL SCAN",       "all systems"),
    ("3", "LIVE DATA",       "realtime stream"),
    ("4", "CLEAR CODES",     "erase DTCs — CAUTION"),
    ("5", "CYLINDER TEST",   "misfire per cylinder"),
    ("6", "CATALYST TEST",   "O2 + catalyst temps"),
    ("7", "EVAP TEST",       "fuel vapor system"),
    ("8", "UDS / VEHICLE",   "manufacturer data"),
    ("9", "SAVED REPORTS",   "browse logs"),
    ("0", "ADAPTER INFO",    "ELM327 status"),
    ("R", "SESSION VAULT",   "recover interrupted scans"),
    ("E", "ECU FINGERPRINT", "probe all ECU addresses"),
]

MENU_ACTIONS = [
    "quick_scan", "full_scan", "live_data", "clear_codes",
    "cylinder_test", "catalyst_test", "evap_test", "uds_scan",
    "report_browser", "adapter_info", "session_vault", "ecu_fingerprint",
]


def run(stdscr, port=None, usb_reset=True):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_GREEN, curses.COLOR_GREEN,  curses.COLOR_BLACK)
    curses.init_pair(C_WARN,  curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(C_ERR,   curses.COLOR_RED,    curses.COLOR_BLACK)
    curses.curs_set(0)
    stdscr.bkgd(" ", curses.color_pair(C_GREEN))

    show_banner(stdscr)

    incomplete = Reporter.find_incomplete()
    if incomplete:
        _session_vault_screen(stdscr, incomplete, port=port, usb_reset=usb_reset)

    plugins = load_plugins()
    elm = _connect_screen(stdscr, port=port, usb_reset=usb_reset)
    if elm is None:
        return

    scanner = Scanner(elm)
    try:
        _main_menu_loop(stdscr, scanner, plugins)
    finally:
        elm.close()


# ── Connection ───────────────────────────────────────────────────────────────

def _connect_screen(stdscr, port=None, usb_reset=True):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD

    _addstr_safe(stdscr, h // 2, (w - 35) // 2, "CONNECTING TO OBD ADAPTER...", bright)
    stdscr.refresh()

    elm = ELM327(port=port)
    try:
        elm.connect(usb_reset=usb_reset)
        _addstr_safe(stdscr, h // 2 + 1, (w - 26) // 2,
                     "[  OK  ] ELM327 CONNECTED", bright)
        stdscr.refresh()
        curses.napms(700)
        return elm
    except ELMConnectionError as e:
        err = "[ FAIL ] {}".format(str(e))
        hint = "Plug in adapter, turn ignition ON, then re-run.  [ any key ]"
        _addstr_safe(stdscr, h // 2 + 1, 2, err[:w - 3],
                     curses.color_pair(C_ERR) | curses.A_BOLD)
        _addstr_safe(stdscr, h // 2 + 3, 2, hint[:w - 3],
                     curses.color_pair(C_WARN))
        stdscr.refresh()
        stdscr.getch()
        return None


# ── Main menu ─────────────────────────────────────────────────────────────────

def _main_menu_loop(stdscr, scanner, plugins):
    sel = 0
    while True:
        _draw_main_menu(stdscr, sel)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            sel = (sel - 1) % len(MENU_ITEMS)
        elif key == curses.KEY_DOWN:
            sel = (sel + 1) % len(MENU_ITEMS)
        elif key in (curses.KEY_ENTER, 10, 13):
            _dispatch(stdscr, sel, scanner, plugins)
        else:
            for i, (num, _, _) in enumerate(MENU_ITEMS):
                if key == ord(num):
                    _dispatch(stdscr, i, scanner, plugins)
                    break


def _draw_main_menu(stdscr, sel):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    green  = curses.color_pair(C_GREEN)
    bright = green | curses.A_BOLD

    box_w = 52
    box_h = len(MENU_ITEMS) + 5
    by = max(0, (h - box_h) // 2)
    bx = max(0, (w - box_w) // 2)

    _draw_box(stdscr, by, bx, box_h, box_w, "OBD-REAPER  MAIN MENU", bright)

    for i, (num, name, desc) in enumerate(MENU_ITEMS):
        row = by + 2 + i
        attr = curses.A_REVERSE | bright if i == sel else green
        line = "  [{}]  {:<16} {}".format(num, name, desc)
        try:
            stdscr.addstr(row, bx + 1, line[:box_w - 2].ljust(box_w - 2), attr)
        except curses.error:
            pass

    footer = "  [↑↓] navigate   [ENTER/0-9] select   [Q] quit"
    try:
        stdscr.addstr(by + box_h - 2, bx + 1, footer[:box_w - 2], green)
    except curses.error:
        pass

    stdscr.refresh()


# ── Action dispatch ───────────────────────────────────────────────────────────

def _dispatch(stdscr, sel, scanner, plugins):
    action = MENU_ACTIONS[sel]

    if action == "live_data":
        _live_data_screen(stdscr, scanner)
        return
    if action == "report_browser":
        _report_browser(stdscr)
        return
    if action == "session_vault":
        incomplete = Reporter.find_incomplete()
        _session_vault_screen(stdscr, incomplete,
                               scanner=scanner, plugins=plugins)
        return
    if action == "uds_scan":
        _uds_plugin_menu(stdscr, scanner, plugins)
        return
    if action == "ecu_fingerprint":
        reporter = Reporter("ecu_fingerprint")
        reporter.start()
        _ecu_fingerprint_screen(stdscr, scanner, reporter)
        try:
            md_path = reporter.finish()
            _show_message(stdscr, "REPORT SAVED: {}".format(os.path.basename(md_path)), 1500)
        except Exception as e:
            _show_message(stdscr, "Save error: {}".format(e), 2000)
        return
    if action == "clear_codes":
        if not _confirm(stdscr, "CLEAR ALL DTCs? This cannot be undone.", "[Y] Yes   [N] No"):
            return

    reporter = Reporter(action)
    reporter.start()
    title = MENU_ITEMS[sel][1]
    gen = getattr(scanner, action)()
    _scan_screen(stdscr, title, gen, reporter)
    try:
        md_path = reporter.finish()
        _show_message(stdscr, "REPORT SAVED: {}".format(os.path.basename(md_path)), 1500)
    except Exception as e:
        _show_message(stdscr, "Save error: {}".format(e), 2000)


# ── Scan screen ───────────────────────────────────────────────────────────────

def _scan_screen(stdscr, title, gen, reporter):
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)

    left_w  = min(30, w // 3)
    right_w = w - left_w - 3
    right_x = left_w + 2

    left_win  = curses.newwin(h - 2, left_w,  1, 0)
    right_win = curses.newwin(h - 2, right_w, 1, right_x)
    log_lines = []
    log_max   = h - 6

    try:
        for pct, label, line in gen:
            if line:
                reporter.checkpoint(line)
                log_lines.append(line)
                if len(log_lines) > log_max * 3:
                    log_lines = log_lines[-log_max:]

            # left panel
            left_win.erase()
            _draw_box_win(left_win, title[:left_w - 4], bright)
            _addstr_win(left_win, 2, 2, "SCANNING...", bright)
            _draw_progress_bar(left_win, 4, 2, left_w - 6, pct, bright)
            _addstr_win(left_win, 6, 2, "CURRENT:", green)
            _addstr_win(left_win, 7, 2, label[:left_w - 4], bright)
            left_win.refresh()

            # right panel
            right_win.erase()
            _draw_box_win(right_win, "LIVE LOG", bright)
            visible = log_lines[-(log_max):]
            log_win_h = right_win.getmaxyx()[0]
            row_offset = 0
            for log_line in visible:
                enriched, severity = _dtc_db.enrich_line(log_line)
                if severity == _dtc_db.CRITICAL:
                    line_attr = curses.color_pair(C_ERR) | curses.A_BOLD
                elif severity == _dtc_db.WARNING:
                    line_attr = curses.color_pair(C_WARN)
                else:
                    line_attr = green
                display_lines = ("> " + enriched).split("\n")
                for j, dl in enumerate(display_lines):
                    row = 2 + row_offset + j
                    if row >= log_win_h - 1:
                        break
                    try:
                        right_win.addstr(row, 2, dl[:right_w - 4], line_attr)
                    except curses.error:
                        pass
                row_offset += len(display_lines)
                if 2 + row_offset >= log_win_h - 1:
                    break
            right_win.refresh()

    except Exception:
        if reporter._chk_file:
            reporter._chk_file.close()
            reporter._chk_file = None
        _show_message(stdscr, "CONNECTION ERROR — partial data saved", 2000)
        return

    _addstr_win(left_win, 2, 2, "COMPLETE    ", bright)
    left_win.refresh()
    curses.napms(700)


# ── Live data screen ──────────────────────────────────────────────────────────

def _live_data_screen(stdscr, scanner):
    h, w = stdscr.getmaxyx()
    green  = curses.color_pair(C_GREEN)
    bright = green | curses.A_BOLD
    warn   = curses.color_pair(C_WARN)

    stdscr.nodelay(True)
    gen = scanner.live_data()

    while True:
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break

        try:
            readings = next(gen)
        except (StopIteration, Exception):
            _show_message(stdscr, "CONNECTION LOST — returning to menu", 2000)
            break

        stdscr.erase()
        header = " LIVE DATA — Press Q to stop "
        _addstr_safe(stdscr, 0, max(0, (w - len(header)) // 2), header, bright)

        _draw_box(stdscr, 1, 2, len(readings) + 4, w - 4, "REALTIME STREAM", bright)

        for i, (name, val) in enumerate(readings.items()):
            row = 3 + i
            line = "  {:<22}  {}".format(name, val)
            _addstr_safe(stdscr, row, 3, line[:w - 6], green)

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        _addstr_safe(stdscr, h - 1, 2, "  Updated: {}".format(ts), warn)
        stdscr.refresh()
        curses.napms(500)

    stdscr.nodelay(False)


# ── Report browser ────────────────────────────────────────────────────────────

def _report_browser(stdscr):
    reports = Reporter.list_reports()
    if not reports:
        _show_message(stdscr, "No saved reports found in reports/", 1500)
        return

    sel = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        bright = curses.color_pair(C_GREEN) | curses.A_BOLD
        green  = curses.color_pair(C_GREEN)

        title = " SAVED REPORTS "
        _addstr_safe(stdscr, 0, 0, title.center(w - 1, "═"), bright)

        for i, (fname, path, size) in enumerate(reports):
            row = 2 + i
            if row >= h - 4:
                break
            attr = curses.A_REVERSE | bright if i == sel else green
            line = "  {:50}  {:>8} B".format(fname[:50], size)
            try:
                stdscr.addstr(row, 0, line[:w - 1].ljust(w - 1), attr)
            except curses.error:
                pass

        incomplete = Reporter.find_incomplete()
        if incomplete:
            msg = "  [!] {} incomplete checkpoint(s) in reports/.checkpoints/".format(
                len(incomplete))
            _addstr_safe(stdscr, h - 3, 0, msg[:w - 1], curses.color_pair(C_WARN))

        _addstr_safe(stdscr, h - 1, 0,
                     "  [↑↓] navigate   [ENTER] view   [Q] back"[:w - 1], green)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            sel = max(0, sel - 1)
        elif key == curses.KEY_DOWN:
            sel = min(len(reports) - 1, sel + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            _, path, _ = reports[sel]
            _view_report(stdscr, path)


def _view_report(stdscr, path):
    try:
        with open(path) as f:
            lines = f.readlines()
    except IOError as e:
        _show_message(stdscr, "Cannot read: {}".format(e), 1500)
        return

    offset = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        bright = curses.color_pair(C_GREEN) | curses.A_BOLD
        green  = curses.color_pair(C_GREEN)
        visible = h - 3

        header = " {} ".format(os.path.basename(path))
        _addstr_safe(stdscr, 0, 0, header.center(w - 1, "═"), bright)

        for i, line in enumerate(lines[offset:offset + visible]):
            try:
                stdscr.addstr(1 + i, 0, line.rstrip()[:w - 1], green)
            except curses.error:
                pass

        footer = "  [↑↓ PgUp PgDn] scroll   [Q] back   Line {}/{}".format(
            offset + 1, len(lines))
        _addstr_safe(stdscr, h - 1, 0, footer[:w - 1], green)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            offset = max(0, offset - 1)
        elif key == curses.KEY_DOWN:
            offset = min(max(0, len(lines) - visible), offset + 1)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - visible)
        elif key == curses.KEY_NPAGE:
            offset = min(max(0, len(lines) - visible), offset + visible)


# ── UDS plugin sub-menu ───────────────────────────────────────────────────────

def _uds_plugin_menu(stdscr, scanner, plugins):
    if not plugins:
        _show_message(stdscr, "No plugins found in plugins/", 1500)
        return

    names = list(plugins.keys())
    sel = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        bright = curses.color_pair(C_GREEN) | curses.A_BOLD
        green  = curses.color_pair(C_GREEN)

        title = " SELECT VEHICLE PLUGIN "
        _addstr_safe(stdscr, 1, max(0, (w - len(title)) // 2), title, bright)

        for i, name in enumerate(names):
            attr = curses.A_REVERSE | bright if i == sel else green
            line = "  {}".format(name)
            try:
                stdscr.addstr(3 + i, 0, line[:w - 1].ljust(w - 1), attr)
            except curses.error:
                pass

        _addstr_safe(stdscr, h - 1, 0,
                     "  [↑↓] navigate   [ENTER] select   [Q] back"[:w - 1], green)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            sel = max(0, sel - 1)
        elif key == curses.KEY_DOWN:
            sel = min(len(names) - 1, sel + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            plugin = plugins[names[sel]]
            mode = "uds_{}".format(plugin.VEHICLE_ID)
            reporter = Reporter(mode)
            reporter.start()
            _scan_screen(stdscr, "UDS: " + names[sel][:20],
                         scanner.uds_scan(plugin), reporter)
            try:
                md_path = reporter.finish()
                _show_message(stdscr, "SAVED: {}".format(os.path.basename(md_path)), 1500)
            except Exception as e:
                _show_message(stdscr, "Save error: {}".format(e), 2000)
            break


# ── ECU Fingerprint screen ────────────────────────────────────────────────────

def _ecu_fingerprint_screen(stdscr, scanner, reporter):
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)
    warn   = curses.color_pair(C_WARN)

    results = [None] * 16  # None = not yet probed; dict = {"status", "ms", "raw"}

    def redraw(current_i, pct):
        stdscr.erase()
        box_w = min(68, w - 2)
        box_h = 16 + 8
        by = max(0, (h - box_h) // 2)
        bx = max(0, (w - box_w) // 2)

        _draw_box(stdscr, by, bx, box_h, box_w,
                  "ECU FINGERPRINT — SYSTEM MAP", bright)
        _draw_progress_bar(stdscr, by + 2, bx + 3, box_w - 8, pct, bright)
        _addstr_safe(stdscr, by + 4, bx + 3,
                     "{:<6} {:<6} {:<9} {:<8} {}".format(
                         "ADDR", "NAME", "STATUS", "TIME", "RESPONSE"),
                     bright)

        for j, addr in enumerate(FINGERPRINT_ADDRS):
            row = by + 5 + j
            name = ECU_NAMES.get(addr, "???")
            res  = results[j]
            if res is None:
                if j == current_i:
                    line = "{:<6} {:<6} ░ PROBING".format(addr, name)
                    attr = warn
                else:
                    line = "{:<6} {:<6} · · ·".format(addr, name)
                    attr = green
            elif res["status"] == "ACTIVE":
                t = "{}ms".format(res["ms"])
                line = "{:<6} {:<6} {:<9} {:<8} {}".format(
                    addr, name, "● ACTIVE", t, res["raw"])
                attr = bright
            else:
                line = "{:<6} {:<6} ○ SILENT   —".format(addr, name)
                attr = green
            try:
                stdscr.addstr(row, bx + 3, line[:box_w - 6], attr)
            except curses.error:
                pass

        stdscr.refresh()

    try:
        gen = scanner.ecu_fingerprint()
        for pct, label, line in gen:
            if line:
                reporter.checkpoint(line)
                parts = line.split()
                # "FINGERPRINT 7E0 ECM ACTIVE 142ms 50 01 ..."
                # "FINGERPRINT 7E0 ECM SILENT —"
                if len(parts) >= 4 and parts[0] == "FINGERPRINT":
                    addr   = parts[1]
                    status = parts[3]
                    idx = FINGERPRINT_ADDRS.index(addr) if addr in FINGERPRINT_ADDRS else -1
                    if idx >= 0:
                        if status == "ACTIVE":
                            ms  = int(parts[4][:-2]) if len(parts) > 4 and parts[4].endswith("ms") else 0
                            raw = " ".join(parts[5:]) if len(parts) > 5 else ""
                            results[idx] = {"status": "ACTIVE", "ms": ms, "raw": raw}
                        else:
                            results[idx] = {"status": "SILENT", "ms": 0, "raw": ""}
            current_i = min(pct * 16 // 100, 15)
            redraw(current_i, pct)
    except Exception:
        if reporter._chk_file:
            reporter._chk_file.close()
            reporter._chk_file = None
        _show_message(stdscr, "CONNECTION ERROR — partial data saved", 2000)
        return

    redraw(16, 100)
    curses.napms(800)


# ── UI helpers ────────────────────────────────────────────────────────────────

def _session_vault_screen(stdscr, incomplete, scanner=None, plugins=None,
                           port=None, usb_reset=True):
    sessions = _vault_parse_sessions(incomplete)
    if not sessions:
        _show_message(stdscr, "NO INTERRUPTED SESSIONS FOUND", 1500)
        return

    sel = 0
    while sessions:
        _vault_draw(stdscr, sessions, sel)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            sel = max(0, sel - 1)
        elif key == curses.KEY_DOWN:
            sel = min(len(sessions) - 1, sel + 1)
        elif key in (ord("s"), ord("S")):
            if _vault_salvage(stdscr, sessions[sel]):
                sessions.pop(sel)
                sel = min(sel, max(0, len(sessions) - 1))
        elif key in (ord("r"), ord("R")):
            active_scanner = scanner
            active_plugins = plugins or {}
            resumed = False
            if active_scanner is None:
                elm = _vault_connect(stdscr, port, usb_reset)
                if elm is None:
                    _show_message(stdscr,
                        "CONNECTION FAILED — press [S] to salvage or [D] to discard",
                        2500)
                    continue
                active_scanner = Scanner(elm)
                active_plugins = load_plugins()
                try:
                    _vault_resume(stdscr, sessions[sel], active_scanner, active_plugins)
                    resumed = True
                except Exception as e:
                    _show_message(stdscr, "RESUME ERROR: {}".format(e), 2000)
                finally:
                    elm.close()
            else:
                try:
                    _vault_resume(stdscr, sessions[sel], active_scanner, active_plugins)
                    resumed = True
                except Exception as e:
                    _show_message(stdscr, "RESUME ERROR: {}".format(e), 2000)
            if resumed:
                sessions.pop(sel)
                sel = min(sel, max(0, len(sessions) - 1))
        elif key in (ord("d"), ord("D")):
            if _confirm(stdscr,
                        "DISCARD checkpoint? All partial data will be lost.",
                        "[Y] Yes   [N] No"):
                os.remove(sessions[sel]["path"])
                sessions.pop(sel)
                sel = min(sel, max(0, len(sessions) - 1))


def _vault_parse_sessions(incomplete):
    sessions = []
    for path in incomplete:
        fname = os.path.basename(path)
        stem = fname[:-4]
        try:
            first_us = stem.index("_")
            second_us = stem.index("_", first_us + 1)
            ts = stem[:second_us]
            mode = stem[second_us + 1:]
        except ValueError:
            continue
        with open(path) as f:
            line_count = sum(1 for ln in f if ln.strip())
        sessions.append({"path": path, "ts": ts, "mode": mode, "lines": line_count})
    return sessions


def _vault_draw(stdscr, sessions, sel):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)
    warn   = curses.color_pair(C_WARN)  | curses.A_BOLD

    box_w = min(74, w - 2)
    box_h = len(sessions) + 12
    by = max(0, (h - box_h) // 2)
    bx = max(0, (w - box_w) // 2)

    _draw_box(stdscr, by, bx, box_h, box_w,
              "REAPER SESSION VAULT — FIELD RECOVERY MODE", bright)
    _addstr_safe(stdscr, by + 2, bx + 3,
                 "!  INTERRUPTED MISSIONS DETECTED — ALL DATA PRESERVED", warn)

    for i, sess in enumerate(sessions):
        row = by + 4 + i
        mode_disp = sess["mode"].upper()[:14]
        ts_disp   = sess["ts"]
        lines     = sess["lines"]
        total     = MODE_TOTALS.get(sess["mode"])
        if total is None and sess["mode"].startswith("uds_"):
            total = MODE_TOTALS.get("uds_scan", 16)
        total = total or 20
        pct    = min(100, int(lines / max(1, total) * 100))
        filled = int(10 * pct / 100)
        bar    = "[" + "█" * filled + "░" * (10 - filled) + "]"
        line   = "  [{:1d}]  {:19}  {:14}  {}  {:3d} ln  {:3d}%".format(
            i + 1, ts_disp, mode_disp, bar, lines, pct)
        attr = curses.A_REVERSE | bright if i == sel else green
        try:
            stdscr.addstr(row, bx + 1, line[:box_w - 2].ljust(box_w - 2), attr)
        except curses.error:
            pass

    sep_row = by + 4 + len(sessions) + 1
    _addstr_safe(stdscr, sep_row,     bx + 2,
                 "─" * (box_w - 4), green)
    _addstr_safe(stdscr, sep_row + 1, bx + 3,
                 "[S]  SALVAGE REPORT  — convert partial data to .md now", green)
    _addstr_safe(stdscr, sep_row + 2, bx + 3,
                 "[R]  RESUME MISSION  — reconnect to vehicle + continue", green)
    _addstr_safe(stdscr, sep_row + 3, bx + 3,
                 "[D]  DISCARD         — delete checkpoint, abort mission", green)
    _addstr_safe(stdscr, sep_row + 4, bx + 3,
                 "[Q]  BACK TO MENU    — [↑↓] navigate sessions", green)
    stdscr.refresh()


def _vault_salvage(stdscr, session):
    _show_message(stdscr, "SALVAGING DATA...", 800)
    try:
        reporter, _ = Reporter.from_checkpoint(session["path"])
        md_path = reporter.finish()
        _show_message(stdscr,
                      "REPORT SAVED: {}".format(os.path.basename(md_path)), 1500)
        return True
    except Exception as e:
        _show_message(stdscr, "SALVAGE FAILED: {}".format(e), 2000)
        return False


def _vault_connect(stdscr, port, usb_reset):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    _addstr_safe(stdscr, h // 2,
                 max(0, (w - 38) // 2),
                 "[ RECONNECTING TO TARGET VEHICLE... ]", bright)
    stdscr.refresh()
    elm = ELM327(port=port)
    try:
        elm.connect(usb_reset=usb_reset)
        return elm
    except ELMConnectionError:
        return None


def _vault_resume(stdscr, session, scanner, plugins):
    mode = session["mode"]
    skip = session["lines"]
    reporter, _ = Reporter.from_checkpoint(session["path"])

    simple_modes = {
        "quick_scan", "full_scan", "cylinder_test", "catalyst_test",
        "evap_test", "adapter_info", "clear_codes", "ecu_fingerprint",
    }
    if mode in simple_modes:
        gen   = getattr(scanner, mode)(skip=skip)
        title = "RESUME: " + mode.upper().replace("_", " ")[:18]
    elif mode.startswith("uds_"):
        vehicle_id = mode[4:]
        plugin = next(
            (p for p in plugins.values() if p.VEHICLE_ID == vehicle_id), None)
        if plugin is None:
            _show_message(stdscr, "PLUGIN NOT FOUND — SALVAGING DATA...", 1000)
            reporter.finish()
            return
        gen   = scanner.uds_scan(plugin, skip=skip)
        title = "RESUME UDS: " + vehicle_id[:14].upper()
    else:
        _show_message(stdscr, "UNKNOWN MODE — SALVAGING DATA...", 1000)
        reporter.finish()
        return

    reporter.start_append()
    _scan_screen(stdscr, title, gen, reporter)
    try:
        md_path = reporter.finish()
        _show_message(stdscr,
                      "MISSION COMPLETE: {}".format(os.path.basename(md_path)),
                      2000)
    except Exception as e:
        _show_message(stdscr, "Save error: {}".format(e), 2000)


def _confirm(stdscr, message, prompt):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    _addstr_safe(stdscr, h // 2,
                 max(0, (w - len(message)) // 2), message[:w - 1],
                 curses.color_pair(C_WARN) | curses.A_BOLD)
    _addstr_safe(stdscr, h // 2 + 2,
                 max(0, (w - len(prompt)) // 2), prompt,
                 curses.color_pair(C_GREEN))
    stdscr.refresh()
    return stdscr.getch() in (ord("y"), ord("Y"))


def _show_message(stdscr, msg, delay_ms):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    _addstr_safe(stdscr, h // 2, max(0, (w - len(msg)) // 2), msg[:w - 1],
                 curses.color_pair(C_GREEN) | curses.A_BOLD)
    stdscr.refresh()
    curses.napms(delay_ms)


def _draw_progress_bar(win, y, x, width, pct, attr):
    filled = max(0, min(width - 7, int((width - 7) * pct / 100)))
    empty  = width - 7 - filled
    bar = "[" + "█" * filled + "░" * empty + "] {:3d}%".format(pct)
    try:
        win.addstr(y, x, bar[:win.getmaxyx()[1] - x - 1], attr)
    except curses.error:
        pass


def _draw_box(win, y, x, h, w, title, attr):
    try:
        win.addstr(y,     x, "╔" + "═" * (w - 2) + "╗", attr)
        for row in range(1, h - 1):
            win.addstr(y + row, x, "║" + " " * (w - 2) + "║", attr)
        win.addstr(y + h - 1, x, "╚" + "═" * (w - 2) + "╝", attr)
        t = " {} ".format(title)
        win.addstr(y, x + max(1, (w - len(t)) // 2), t[:w - 2], attr)
    except curses.error:
        pass


def _draw_box_win(win, title, attr):
    h, w = win.getmaxyx()
    _draw_box(win, 0, 0, h, w, title, attr)


def _addstr_safe(win, y, x, text, attr):
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def _addstr_win(win, y, x, text, attr):
    h, w = win.getmaxyx()
    try:
        win.addstr(y, x, text[:w - x - 1], attr)
    except curses.error:
        pass
