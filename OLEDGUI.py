#!/usr/bin/env python3

#
# OLED display bitmap editor
#

import sys
from tkinter import *
from tkinter import messagebox
from tkinter import filedialog
from os import path
from socket import *
import struct
from PIL import Image, ImageTk

#
# window definition
#


class EditorWindow():
    def __init__(self, parent=None, name=''):
        win = Tk()
        win.title('OLED Picture Editor')
        win.protocol('WM_DELETE_WINDOW', self.cmdQuit)  # intercept Ctrl_Q and Close Window button
        win.minsize(500, 400)
        win.maxsize(500, 400)

        self.win = win
        self.hexFormat = FALSE
        self.maxWidth = 128
        self.maxHeight = 64

        sf = 16
        self.sf = sf

        wx = 16
        wy = 16
        self.wx = wx
        self.wy = wy
        self.array = [0 for x in range(wx // 8 * wy)]
        self.modified = False

        Label(win, text='Filename:').grid(padx=5, pady=5, row=1, column=0, sticky=W)

        self.filename = StringVar()
        self.filename.set(name)

        e = Entry(win, width=24, takefocus=YES, textvariable=self.filename)
        e.place(x=80, y=5)
        # e.grid(padx=5, pady=5, row=1, column=1, sticky=W)
        e.focus_set()   # take over input from other windows, select address field
        e.icursor(END)  # set cursor after last digit

        Checkbutton(win, text='Format hex', takefocus=YES, command=self.cmdSetFormat).grid(padx=5, pady=5, row=1, column=2)

        Button(win, text='Load', takefocus=YES, command=self.cmdLoad).grid(padx=5, pady=5, row=2, column=0, sticky=W)
        Button(win, text='Import', takefocus=YES, command=self.cmdImport).grid(padx=5, pady=5, row=2, column=1, sticky=W)
        Button(win, text='Send', takefocus=YES, command=self.cmdSend).grid(padx=5, pady=5, row=2, column=2, sticky=W)
        Button(win, text='Save', takefocus=YES, command=self.cmdSave).grid(padx=5, pady=5, row=2, column=3, sticky=W)

        Button(win, text='FlipVert', takefocus=YES, command=self.cmdFlipV).grid(padx=5, pady=5, row=3, column=0, sticky=W)
        Button(win, text='FlipHoriz', takefocus=YES, command=self.cmdFlipH).grid(padx=5, pady=5, row=3, column=1, sticky=W)
        # self.labelPos = Label(win, text='Test')
        # self.labelPos.grid(padx=5, pady=5, row=3, column=2, sticky=W)

        # ------- draw canvas ----------------------------

        # Received image canvas
        rxBitmap = Canvas(win, width=self.maxWidth + 20, height=self.maxHeight + 20, relief='flat', bg='black')
        rxBitmap.grid(padx=5, row=4, column=0, sticky=NW)
        self.rxImg = Image.new('RGB', (self.maxWidth, self.maxHeight))
        self.tkImg = ImageTk.PhotoImage(self.rxImg)
        rxBitmap.create_image(10, 10, image=self.tkImg, state='normal', anchor=NW)
        self.rxBitmap = rxBitmap

        # Editor canvas
        brd = 2
        self.brd = brd
        graph = Canvas(win, width=(wx)*sf, height=(wy)*sf, relief='flat', bd=brd, bg='gray')
        graph.grid(padx=5, row=4, column=1, columnspan=2)
        graph.bind('<Button-1>', self.cmdToggle)   # capture mouse button inside canvas
        graph.bind('<B1-Motion>', self.cmdDrag)
        graph.bind('<B2-Motion>', self.cmdClear)
        graph.bind('<B3-Motion>', self.cmdClear)
        self.graph = graph

        # Editor preview canvas
        self.scale = 2
        bmp = Canvas(win, width=10 + self.wx * self.scale, height=10 + self.wy * self.scale, relief='flat', bg='black')
        # bmp.grid(padx=5, row=4, column=3, sticky=NW)
        bmp.place(x=110, y=200)
        self.bmpImg = Image.new('RGB', (self.wx, self.wy))
        self.bmptkImg = ImageTk.PhotoImage(self.bmpImg.resize((self.wx * self.scale, self.wy * self.scale)))
        bmp.create_image(6, 6, image=self.bmptkImg, state='normal', anchor=NW)
        self.bmp = bmp

        # Label with device IP:port
        self.labelIP_txt = 'Device IP: '
        self.labelIP = Label(win, text='Device not found')
        self.labelIP.grid(padx=5, pady=5, row=5, columnspan=3, sticky=W)

        if name != '':
            self.cmdLoad()
        self.drawPicture()

        self.port = 6661
        self.devAddr = ('', '')
        self.udp = socket(AF_INET, SOCK_DGRAM)
        self.udp.bind(('', self.port))
        self.udp.settimeout(0.0)

        self.udp_rx_cnt_timeout = 10
        self.udp_rx_cnt = self.udp_rx_cnt_timeout
        self.devThreadRun = 250

    def bgDeviceListen(self):
        ew.win.after(self.devThreadRun, self.bgDeviceListen)
        arrayRx = None
        try:
            arrayRx, self.devAddr = self.udp.recvfrom(1024)
            self.udp_rx_cnt = self.udp_rx_cnt_timeout
        except:
            if self.udp_rx_cnt > 0:
                self.udp_rx_cnt -= 1
            else:
                self.devAddr = ('', '')

        addrStr = 'Device not found' if self.devAddr[0] == '' else self.labelIP_txt + f'{self.devAddr[0]}:{self.devAddr[1]}'
        # print(f'{addrStr}')

        if arrayRx != None:
            for x in range(self.maxWidth):
                for y in range(self.maxHeight):
                    p = (arrayRx[x + ((y//8) * self.maxWidth)] & (1 << (y & 7)))
                    self.rxImg.putpixel((x, y), (255, 255, 255) if p else (0, 0, 0))
            self.tkImg.paste(self.rxImg)

        self.labelIP.config(text=addrStr)
        # self.labelIP.update()
        color = 'red' if (self.udp_rx_cnt == 0) else 'black'
        self.rxBitmap.create_rectangle(0, 0, self.rxBitmap.winfo_width(), self.rxBitmap.winfo_height(), outline=color, width=10, state=NORMAL)
        # self.rxBitmap.update()

    def cmdSend(self):
        if self.devAddr[0] == '':
            print('Device not found')
            return

        bmpType = 0  # Type 0 -> simple bitmap
        xpos = (self.maxWidth - self.wx) // 2
        ypos = (self.maxHeight - self.wy) // 2
        data = bytearray(self.array)
        pkt = struct.pack('<BBBBBB1024s', 1, bmpType, xpos, ypos, self.wx, self.wy, data)

        if self.udp.sendto(pkt, self.devAddr) > 0:
            print(f'Bitmap sent to device @ {self.devAddr[0]}:{self.devAddr[1]}')

    def cmdShowPos(self, event):
        posStr = f'X:{event.x} Y:{event.y}'
        self.labelPos.config(text=posStr)

    # -------------------- Graphs methods
    def drawPicture(self):
        for y in range(self.wy):
            for x in range(self.wx):
                self.drawPixel(x, y)

    def getPixel(self, x, y):
        return self.array[(x >> 3) + y * (self.wx >> 3)] & (0x80 >> (x & 7)) != 0

    def setPixel(self, x, y):
        self.array[(x >> 3) + y * (self.wx >> 3)] |= (0x80 >> (x & 7))
        self.drawPixel(x, y)

    def setPixel(self, x, y, v):
        if (v):
            self.array[(x >> 3) + y * (self.wx >> 3)] |= (0x80 >> (x & 7))
        else:
            self.array[(x >> 3) + y * (self.wx >> 3)] &= ~(0x80 >> (x & 7))
        self.drawPixel(x, y)

    def invPixel(self, x, y):
        self.array[(x >> 3) + y * (self.wx >> 3)] ^= (0x80 >> (x & 7))
        self.drawPixel(x, y)

    def drawPixel(self, x, y):
        sf = self.sf
        brd = 1+self.brd
        p = self.getPixel(x, y)
        self.graph.create_rectangle(brd+x*sf, brd+y*sf, brd+(x+1)*sf, brd+(y+1)*sf, fill='white' if p else 'black')
        self.bmpImg.putpixel((x, y), (255, 255, 255) if p else (0, 0, 0))
        self.bmptkImg.paste(self.bmpImg.resize((self.wx * self.scale, self.wy * self.scale), Image.BOX))

    def cmdToggle(self, event):
        x = int((self.graph.canvasx(event.x)-1-self.brd)/self.sf)
        y = int((self.graph.canvasy(event.y)-1-self.brd)/self.sf)
        if x < self.wx and y < self.wy:
            self.invPixel(x, y)
            self.modified = True

    def cmdDrag(self, event):
        x = int((self.graph.canvasx(event.x)-1-self.brd)/self.sf)
        y = int((self.graph.canvasy(event.y)-1-self.brd)/self.sf)
        if x < self.wx and y < self.wy:
            self.setPixel(x, y, True)
            self.modified = True

    def cmdClear(self, event):
        x = int((self.graph.canvasx(event.x)-1-self.brd)/self.sf)
        y = int((self.graph.canvasy(event.y)-1-self.brd)/self.sf)
        if x < self.wx and y < self.wy:
            self.setPixel(x, y, False)
            self.modified = True

    def cmdFlipV(self):
        lwx = self.wx // 8
        for y in range(0, self.wy // 2):
            for x in range(lwx):
                yo = self.wy - 1 - y
                t = self.array[x + y * lwx], self.array[x + yo * lwx]
                self.array[x + yo * lwx], self.array[x + y * lwx] = t
        self.drawPicture()
        self.modified = True

    def cmdFlipH(self):
        for y in range(0, self.wy):
            for x in range(self.wx // 2):
                xo = self.wx - 1 - x
                p1 = self.getPixel(x, y)
                p2 = self.getPixel(xo, y)
                self.setPixel(x, y, p2)
                self.setPixel(xo, y, p1)
        self.drawPicture()
        self.modified = True

    def cmdImport(self):
        THR = THG = THB = 1
        if self.modified:
            if not messagebox.askokcancel('Import', 'Unsaved changes will be lost!\n Are you sure?', icon='warning'):
                return
        filename = self.filename.get()
        base, ext = path.splitext(filename)
        if ext == '':
            ext = '.gif'
        if ext != '.gif':
            messagebox.showinfo('Error', 'Only GIF files can be imported!', icon='warning')
            return
        filename = base + ext
        try:
            photo = PhotoImage(file=filename)
        except:
            print('Could not import image file:', filename)
        else:
            wx = min(self.wx, photo.width())
            wy = min(self.wy, photo.height())
            for y in range(wy):
                for x in range(wx):
                    r, g, b = map(lambda x: int(x), photo.get(x, y).split())
                    if (r, g, b) == (0, 0, 0) or (r, g, b) == (255, 255, 255):
                        continue  # discard transparent and white
                    if r > THR or g > THG or b > THB:
                        self.setPixel(x, y)
            print('File %s imported successfully' % filename)
            self.modified = False

    def cmdLoad(self):
        if self.modified:
            if not messagebox.askokcancel('Load', 'Unsaved changes will be lost,\n are you sure?', icon='warning'):
                return

        fname = filedialog.askopenfilename(initialdir=".", initialfile=self.filename.get(), title="Select file",
                                           filetypes=(('header files', '*.h'), ('all files', '*.*')))
        if fname is not None:
            # print(f'>>>>{fname}')
            self.filename.set(fname.split('/')[-1])

            # Open and process file
            i = 0
            last = (self.wx // 8 * self.wy)
            try:
                with open(self.filename.get()) as f:
                    ch = f.read(1)
                    while ch != '{':
                        ch = f.read(1)
                    while i < last:
                        ch = f.read(1)
                        while ch < '0':
                            ch = f.read(1)
                        if ch != '0':
                            if ch == '}':
                                self.drawPicture()
                                self.modified = False
                                return
                            else:
                                break
                        ch = f.read(1)
                        if ch == 'x':
                            s = f.read(2)
                            try:
                                self.array[i] = int('0x'+s, base=16)
                            except ValueError:
                                break
                        elif ch == 'b':
                            s = f.read(8)
                            try:
                                self.array[i] = int('0b'+s, base=2)
                            except ValueError:
                                break

                        i += 1
                    else:
                        print('File loaded successfully')
                        self.drawPicture()
                        self.modified = False
                        return
                    print('File format could not be recognized!')
            except IOError:
                print('File %s not found' % self.filename.get())

    def cmdSave(self):
        filename = self.filename.get()
        if path.isfile(filename):
            if not messagebox.askokcancel('Save', 'File %s already exist!\n Overwrite?' % filename):
                return

        if len(filename) == 0:
            filename = filedialog.asksaveasfilename(initialdir=".", initialfile=self.filename.get(), title="Select file",
                                                    filetypes=(('header files', '*.h'), ('all files', '*.*')))
            if filename == '' or filename == ():
                return

        base, ext = path.splitext(filename)
        if ext != '.h':
            messagebox.showinfo('Error', 'Only .h files can be generated!', icon='warning')
            return

        filename = base + ext
        self.filename.set(filename.split('/')[-1])
        try:
            with open(filename, "wt") as f:
                f.write('/*\n')
                f.write(' *  Arduino OLED display bitmap \n')
                f.write(' *  %s x %s \n' % (self.wx, self.wy))
                f.write(' */ \n')
                f.write('static const unsigned char PROGMEM %s[] = { \n' % base)
                if self.hexFormat:
                    for x in range(0, self.wx * self.wy//8, 16):
                        for k in range(16):
                            f.write('0x%02x, ' % self.array[x + k])
                        f.write('\n')
                else:
                    for x in range(0, self.wx * self.wy//8, 2):
                        for k in range(2):
                            f.write("0b{0:08b},".format(self.array[x + k]))
                        f.write('\n')
                f.write('};\n')
                self.modified = False
        except IOError:
            print('Cannot write file:', filename)

    def cmdSetFormat(self):
        self.hexFormat = not self.hexFormat

    def cmdQuit(self):
        if self.modified:
            if not messagebox.askokcancel("Quit", "There are unsaved changes,\n are you sure?"):
                return
        self.win.quit()


if __name__ == '__main__':
    filename = ''
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    ew = EditorWindow(name=filename)
    ew.win.after(100, ew.bgDeviceListen)
    ew.win.mainloop()
