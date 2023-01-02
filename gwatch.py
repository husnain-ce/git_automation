import os
from watchfiles import watch
import ctypes   
import subprocess
from datetime import datetime

def watcher(branch, path):
    for _ in watch(path):
        result = subprocess.run(['git', 'diff', '--name-only'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if result:
            MB_SYSTEMMODAL = 0x00001000
            r = ctypes.windll.user32.MessageBoxW(0, "Publish Changes", "Do you wish to publish these changes?", 1 | MB_SYSTEMMODAL)
            if r == 1:
                os.system("git add -A")
                os.system(f'git commit -m "Auto Publish Update {datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}"')
                # No remote set
                if branch:
                    os.system("git push")

if __name__ == "__main__":
    watcher()
