import os

def lock_pc():
    os.system("rundll32.exe user32.dll,LockWorkStation")
