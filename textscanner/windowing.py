import sys


def set_titlebar_color(window, hex_color, dark=True):
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        color = hex_color.lstrip("#")
        red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
        colorref = ctypes.c_int((blue << 16) | (green << 8) | red)
        hwnd = wintypes.HWND(window.winfo_id())
        user32 = ctypes.windll.user32
        hwnd = wintypes.HWND(user32.GetAncestor(hwnd, 2))
        dwm = ctypes.windll.dwmapi
        dark_flag = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(dark_flag), ctypes.sizeof(dark_flag)
            ) == 0:
                break
        for attribute in (35, 34):
            dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(colorref), ctypes.sizeof(colorref)
            )
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        return True
    except (AttributeError, OSError, ValueError):
        return False
