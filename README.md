<p align="center">
  <img src="docs/icon.png" width="128" alt="Pomme icon">
</p>

<h1 align="center">Pomme</h1>

<p align="center">A pomodoro timer with a glass apple you can spin.<br>Work while it gets eaten. Take a break when it's down to the core.</p>

<p align="center">
  <a href="https://github.com/CyberOil1997/pomme/releases/latest"><b>Download for Mac</b></a>
</p>

<p align="center">
  <img src="docs/screenshot.png" width="320" alt="Pomme halfway through a focus session">
  &nbsp;
  <img src="docs/green.png" width="320" alt="Pomme with the green apple">
</p>

## How it works

Press Start and get to work. Over a 25 minute focus session the apple gets eaten bite by bite, and when the timer runs out all that's left is the core. Then you get a short break. A fresh apple is waiting when you come back.

<p align="center">
  <img src="docs/stages.jpg" alt="The apple from whole to core">
</p>

**Focus** is for work. **Short break** is time off, so get up and grab some water. After 4 focus rounds you get a **long break**. All of these lengths can be changed in settings.

Some other things:

- Drag the apple to spin it. Flick it and it keeps going for a while. Tap it and it rings like glass.
- Each bite plays a little note, and the notes climb as the apple gets smaller.
- There's a red apple and a green one.
- The time shows in your menu bar, so you can close the window and keep going.
- Keyboard: `Space` starts or pauses, `R` resets, `S` skips, and `1` `2` `3` switch modes.

<p align="center">
  <img src="docs/settings.png" width="320" alt="Settings">
</p>

## The apple is a real 3D model

None of the art is drawn in code. The apple, the plinth and the room around it were all modeled and rendered in Blender. The apple is a glass model with a gold stem and a glass leaf. The bites are cut with a model of human front teeth at real size, so they look like actual bites. The app shows the model live with three.js, which is why it spins smoothly.

Everything comes from one script, [`blender/apple.py`](blender/apple.py). To rebuild the assets:

```sh
blender -b -P blender/apple.py -- --mode export --out export
blender -b -P blender/apple.py -- --mode backdrop --color red --res 2400 --samples 64 --out backdrop
blender -b -P blender/apple.py -- --mode backdrop --color green --res 2400 --samples 64 --out backdrop
```

The sound effects are synthesized in the app with Web Audio, all tuned to the same key. The one recorded sound is the apple crunch, made with Higgsfield. The font is [Pretendard](https://github.com/orioncactus/pretendard).

## Install

Download the `.dmg` from [Releases](https://github.com/CyberOil1997/pomme/releases/latest), open it and drag Pomme into Applications.

The app isn't notarized by Apple yet, so the first time you open it macOS will say it can't check it. Right-click Pomme in Applications, choose **Open**, then **Open** again. You only have to do this once.

## Build it yourself

```sh
cd app
npm install
npm start        # run it
npm run dist     # build the .dmg into app/dist
```

## License

MIT
