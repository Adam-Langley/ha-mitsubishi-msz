# Brand assets

The Mitsubishi three-diamond mark, drawn geometrically by `make_icon.py`
(three 60 degree rhombi at 120 degree intervals) rather than traced, so it can
be regenerated at any size.

| File | Size | Purpose |
| --- | --- | --- |
| `icon.png` | 256x256 | Integration icon |
| `icon@2x.png` | 512x512 | Retina icon |
| `logo.png` | 256x256 | Integration logo |
| `logo@2x.png` | 512x512 | Retina logo |

Home Assistant does not read these from the integration itself — it loads
brand images from `brands.home-assistant.io` by domain. To make the icon
appear, these files have to be contributed to the
[home-assistant/brands](https://github.com/home-assistant/brands) repository
under `custom_integrations/mitsubishi_msz/`. Until then Home Assistant shows
its "icon not available" placeholder.

The mark is a trademark of Mitsubishi Electric and is used here only to
identify the hardware this integration talks to.
