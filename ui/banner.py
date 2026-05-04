import curses

BANNER = [
    "  ██████╗ ██████╗ ██████╗       ██████╗ ███████╗ █████╗ ██████╗ ███████╗██████╗  ",
    " ██╔═══██╗██╔══██╗██╔══██╗      ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗ ",
    " ██║   ██║██████╔╝██║  ██║█████╗██████╔╝█████╗  ███████║██████╔╝█████╗  ██████╔╝ ",
    " ╚██████╔╝██╔══██╗██████╔╝      ██║  ██║██╔══╝  ██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗ ",
    "  ╚═════╝ ╚═╝  ╚═╝╚═════╝       ╚═╝  ╚═╝███████╗██║  ██║██║     ███████╗██║  ██║ ",
    "                                         ╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝",
]
SUBTITLE = "[ VEHICLE DIAGNOSTIC SYSTEM v1.0 ]   [ ELM327 PROTOCOL ]   [ sudo python3 reaper.py ]"


def show_banner(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(1) | curses.A_BOLD
    green  = curses.color_pair(1)

    start_row = max(0, h // 2 - len(BANNER) // 2 - 3)

    for i, line in enumerate(BANNER):
        col = max(0, (w - len(line)) // 2)
        try:
            stdscr.addstr(start_row + i, col, line[:w - 1], bright)
        except curses.error:
            pass

    sub_col = max(0, (w - len(SUBTITLE)) // 2)
    try:
        stdscr.addstr(start_row + len(BANNER) + 1, sub_col, SUBTITLE[:w - 1], green)
    except curses.error:
        pass

    init_text = "  INITIALIZING REAPER..."
    init_row = start_row + len(BANNER) + 3
    init_col = max(0, (w - len(init_text)) // 2)
    for i, ch in enumerate(init_text):
        try:
            stdscr.addstr(init_row, init_col + i, ch, bright)
            stdscr.refresh()
        except curses.error:
            pass
        curses.napms(35)

    curses.napms(400)
    press = "[ PRESS ANY KEY ]"
    press_col = max(0, (w - len(press)) // 2)
    try:
        stdscr.addstr(init_row + 1, press_col, press, green | curses.A_BLINK)
        stdscr.refresh()
    except curses.error:
        pass

    stdscr.nodelay(False)
    stdscr.getch()
