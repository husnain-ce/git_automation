from asyncio import subprocess
from datetime import datetime
import ctypes   
import os
import stat
import subprocess
import shutil
import json

TEMP_DIR = '.temp'
MB_SYSTEMMODAL = 0x00001000

def pull(info):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    with open('logs.txt', 'a') as logs:
        # Get changes
        meta = {}
        try:
            if os.path.exists(f'../{TEMP_DIR}') and os.path.isdir(f'../{TEMP_DIR}'):
                error(f"Hey! a folder named {TEMP_DIR} already exists in the parent directory. Please remove it and try again.")
                return
            shutil.copytree('.git', f'../{TEMP_DIR}/.git', dirs_exist_ok=True)
            curr_dir = os.getcwd()
            os.chdir(f'../{TEMP_DIR}')
            process = subprocess.Popen(['git', 'reset', '--hard'], shell=False, stdout=logs, stderr=logs, startupinfo=si)
            process.wait()
            process = subprocess.Popen(['git', 'pull'], shell=False, stdout=logs, stderr=logs, startupinfo=si)
            process.wait()
            os.chdir(curr_dir)
            if os.path.exists(f'../{TEMP_DIR}/.autopublish'):
                with open(f'../{TEMP_DIR}/.autopublish', 'r') as f:
                    meta = json.load(f)
            rmtree(f'../{TEMP_DIR}')
        except Exception as ex:
            error(f"Failed to get updates into the parent {TEMP_DIR} folder, check permissions and try again.")
            logs.write(str(ex))
            return
        # Check if there are changes
        if info.get("Tag") == meta.get("Tag"):
            logs.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M %p')} Everything is on the version {meta.get('Tag')}!")
            return
        # Prompt user to update
        r = ctypes.windll.user32.MessageBoxW(0, meta.get("UpdateMessage", "Exciting new updates!"), f"Update to {meta.get('Tag', 'v1.0.0')}", 1 | MB_SYSTEMMODAL)
        if r == 1:
            process = subprocess.Popen(['git', 'reset', '--hard'], shell=False, stdout=logs, stderr=logs, startupinfo=si)
            process.wait()
            process = subprocess.Popen(['git', 'pull'], shell=False, stdout=logs, stderr=logs, startupinfo=si)
            process.wait()
            success(f"Updated to version {meta.get('Tag', 'v1.0.0')}")
        else:
            error(f"Denied an update to {meta.get('Tag', 'v1.0.0')} :(")

def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)

def error(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Error", 0 | MB_SYSTEMMODAL)
    
def success(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Yay", 0 | MB_SYSTEMMODAL)