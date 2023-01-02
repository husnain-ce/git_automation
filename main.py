from gooey import Gooey, GooeyParser
import json
import os
import signal
import subprocess

@Gooey(shutdown_signal=signal.CTRL_C_EVENT, show_stop_warning=False)
def main():
    # Clear older logs
    os.remove('logs.txt') if os.path.exists('logs.txt') else None
    # Load config
    defaults = {}
    try:
        if os.path.exists('.autopublish'):
            with open('.autopublish', 'r') as f:
                defaults = json.load(f)
        if os.path.exists(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config")):
            with open(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config"), 'r') as f:
                defaults.update(json.load(f))
    except Exception:
        pass
    parser = GooeyParser(description='Auto Publish')
    parser.add_argument('--URL', help='Remote Github URL', default=defaults.get('URL'))
    parser.add_argument('--Wait', help='Wait duration (minutes)', type=int, default=defaults.get('Wait', 5))    
    parser.add_argument('Branch', help='Branch to watch', default=defaults.get('Branch', 'main'))
    parser.add_argument('Path', help='Project Folder', default=defaults.get('Path'), widget="FileChooser")
    parser.add_argument('WinPassword', help='Windows Login Password', widget="PasswordField")
    parser.add_argument('--Username', help='Git Username', default=defaults.get('Username'))
    parser.add_argument('--Password', help='Git Password', default=defaults.get('Password'))
    args = parser.parse_args()
    for arg in args.__dict__:
        defaults[arg] = args.__dict__[arg]
    if "Path" in defaults:
        defaults["Path"] = os.path.abspath(defaults["Path"])
    with open('.autopublish', 'w') as f:
        f.write(json.dumps({
            "URL": defaults.get("URL"),
            "Branch": defaults.get("Branch"),
            "Tag": defaults.get("Tag"),
            "UpdateMessage": defaults.get("UpdateMessage"),
        }, indent=2))
    os.makedirs(os.path.join("C:\\", "ProgramData", "autoupdater"), exist_ok=True)
    with open(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config"), "w") as f:
        f.write(json.dumps({
            "Path": defaults.get("Path"),
            "Wait": defaults.get("Wait"),
            "Username": defaults.get("Username"),
            "Password": defaults.get("Password")
        }, indent=2))

    process = subprocess.Popen(["service.exe", "stop"], shell=False)
    process.wait()
    process = subprocess.Popen(["service.exe", "remove"], shell=False)
    process.wait()
    process = subprocess.Popen(["service.exe", f'--username={os.environ["COMPUTERNAME"]}\\{os.getlogin()}', f'--password={args.WinPassword}', "--startup=auto", "install"], shell=False)
    process.wait()
    process = subprocess.Popen(["sc", "start", "AppUpdaterService"], shell=False, stdout=subprocess.PIPE)
    process.wait()
    output = process.communicate()[0].decode('utf-8')
    if "FAILED" in output:
        print("Unable to create & start service. Are you sure the password is correct?")
        print("\nYou can manually create the service by running the following command:")
        print(f'    service.exe --username="{os.environ["COMPUTERNAME"]}\\{os.getlogin()}" --password="MY PASSWORD" --startup=auto install')
        print("If you are still having issues, please contact the developer.\n")
        print(output)
    
if __name__ == "__main__":
    main()