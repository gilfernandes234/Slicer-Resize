# Sprite Editor 

- Resize (Nearest, Lanczos, Bicubic and Bilinear
- Color Adjust
- Background Remove
- Paint Brush
- Slicer Png
- Eraser
- Rotate
- Flip
- Selection tools
- Outline/Adjust
- Layer Panel
- Denoise
- Upscale (Waifu2x and Real-ESRGRAN)
- Export
- Pixel Snap
- Sharpering
- Remove Pixel Opacity



```bash
# Instalar dependências
- Python 3.10+

py -m pip install -r requirements.txt

# Executar 
py spriteEditor.py
```



```bash
Need .exe?

py -m nuitka spriteEditor.py ^
 --onefile ^
 --windows-console-mode=disable ^
 --enable-plugin=pyqt6 ^
 --windows-icon-from-ico="editor.ico" ^
 --include-package=PIL ^
 --include-package=torch ^
 --include-package=basicsr ^
 --include-package=realesrgan ^
 --assume-yes-for-downloads ^
 --low-memory
```


https://github.com/user-attachments/assets/5d31c869-5efe-46cf-8c6f-16cb20dece51


