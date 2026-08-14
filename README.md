# VeeamDesigner
Create Veeam Design Diagram &amp; Firewall configurations (POC).

## Disclaimer

This project is a personal learning exercise and is provided as-is, with no guarantees at all.

Updates may change file formats, database schemas, or behavior without notice. Always keep a copy of your customizations and project files (`.vd`, `.db`, `.drawio`) before updating.

Given the subject matter — designing Veeam backup infrastructure — the author is acutely aware of the irony of recommending backups, but...  please, **back up your data.**

## Documentation

See [walkthrough.md](walkthrough.md) for the full guide.

I tried really hard to document the project so that you can get the gist of the tool, and provide some samples so you can take a look without even running any tool.

# Third-party components and acknowledgements

VeeamDesigner relies on several third-party libraries, tools, fonts, and reference projects.

All trademarks and copyrights belong to their respective owners.

---

## Python libraries

| Library | Purpose |
| :-- | :-- |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parsing |
| [N2G](https://github.com/dmulyalin/N2G) | Draw.io diagram generation |
| [Flask](https://flask.palletsprojects.com/) | Web server for Ports Explorer |

---

## Graphical Elements

| Component | Purpose |
| :-- | :-- |
| Veeam (https://www.veeam.com/company/brand-resource-center.html) | Veeam Brand Resource Center Architecture Icons |

---

## Frontend libraries and assets

| Component | Purpose |
| :-- | :-- |
| [HTMX](https://htmx.org) | Dynamic partial page updates in Ports Explorer |
| [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) | Monospace UI font |
| [Syne](https://fonts.google.com/specimen/Syne) | Sans-serif UI font |


Fonts are loaded through Google Fonts CDN.

---

## External tools

These tools are not bundled with the project but are useful during development or usage.

| Tool | Purpose |
| :-- | :-- |
| [DB Browser for SQLite](https://sqlitebrowser.org) | Inspect and manage SQLite databases |
| [Draw.io / diagrams.net](https://app.diagrams.net) | Open and arrange generated `.drawio` diagrams |

---

## Reference and inspiration projects

| Project | Notes |
| :-- | :-- |
| [MagicPorts](https://magicports.veeambp.com/) | General inspiration for ports visualization and exploration workflows |
| [Ports App Backend](https://github.com/shapedthought/ports_server) | Original inspiration/source for the database schema |

---

## Contibutors

The code and documentation were developed, drafted and revised with assistance from Claude (Anthropic).

---

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

See the `LICENSE` file for details.

Third-party components remain licensed under their respective licenses.

---

## Copyright

Copyright (c) 2026 strangenewcoder

