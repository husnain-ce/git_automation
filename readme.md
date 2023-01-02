How to use updater:
    - Run configure.exe and input all data required

How to build updater:
    - env/Scripts/activate.bat
    - pip install -r requirements.txt
    - pyinstaller build.spec
    - pyinstaller build.service.spec
    
    Move dist/configure.exe and dist/service.exe to parent folder