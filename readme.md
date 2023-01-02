How to use updater:
    - Run updater.exe and input all data required

How to build updater:
    - env/Scripts/activate.bat
    - pip install -r requirements.txt
    - pyinstaller build.spec
    
    Move dist/updater.exe to parent folder

Note:
    - A directory is created in C:\ProgramData\autoupdater for all of the intermediate operations
    - A file called .autopublish must be present and updated at the remote repository
        {
            "URL": "https://github.com/hello/world.git",
            "Branch": "main",
            "Tag": "v1.0.0",
            "UpdateMessage": "Changes in v1.0.0: \r\n\r\n* Better everything!!"
        }
      The Tag and UpdateMessage need to be updated for updates to work
    - Git username and password may be specified optionally in C:\ProgramData\autoupdater\.autopublish.config as follows:
        {
            "URL": "https://github.com/hello/world.git",
            "Path": "C:\\Users\\hello\\project",
            "Username": "hello",
            "Password": "world"
        }
    - The updater will not update itself - the updater needs to be kept separate from the files to update
