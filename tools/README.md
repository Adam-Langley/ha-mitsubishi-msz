# Brand assets

`make_icon.py` draws the Mitsubishi three-diamond mark geometrically — three
60 degree rhombi at 120 degree intervals — rather than tracing a bitmap, so it
can be regenerated at any size:

```bash
python3 tools/make_icon.py
```

It writes `icon.png` (256x256), `icon@2x.png` (512x512) and matching `logo`
variants into `custom_components/mitsubishi_msz/brand/`.

Home Assistant 2026.3 and later reads brand images from a `brand/` folder
inside the integration and gives them priority over the brands CDN, so no
contribution to [home-assistant/brands](https://github.com/home-assistant/brands)
is needed. On older versions the icon falls back to the CDN placeholder.

The mark is a trademark of Mitsubishi Electric and is used here only to
identify the hardware this integration talks to.
