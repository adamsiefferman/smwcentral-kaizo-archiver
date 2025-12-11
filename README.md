# A tool to download and patch and generally archive the kaizo section at smwcentral.net using their public API

This tool is primarily for Linux users, but if you are a Windows user you can look up how to install WSL2 and download one of the many available distro's to use this script.

You will need to head over to the Flips GitHub repo https://github.com/Alcaro/Flips/releases and download the latest linux release. Make sure to put the `flips` binary in the same folder as the script and do `chmod +x flips` to make it executable.

You will also need to provide your own Super Mario World base rom to patch against and also place it in the same folder as the script as `clean.smc`. I named mine clean.smc because I used ucon64 to make it headerless.
That last step of removing the header should not be necessary for using this tool, but it is just something I did to have a rom for LunarMagic if I am not mistaken. 

running `./smwcentral-kaizo-archiver.py --help` will provide further instruction. The script will download, extract and patch the roms. Playable roms are in the patched dir and the original zips and bps patch files are retained. The script can download kaizo hacks from the awaiting moderation section i.e. hacks that have not been officially moderated and released. If you only want to download one section just use `--section` so for example `./smwcentral-kaizo-archiver.py --advanced`. 

This script has no requirements or dependencies beyond the standard Python library and the `flips` binary plus the need for a smw base rom to patch against. 

```
usage: smwcentral-kaizo-archiver.py [-h] [--all] [--newcomer] [--casual] [--intermediate] [--advanced] [--expert] [--master]
                                    [--grandmaster] [--awaiting] [--base-dir BASE_DIR] [--clean-rom CLEAN_ROM] [--flips FLIPS]

Archive Kaizo hacks from SMWCentral. Downloads, extracts .bps files, and patches them.

options:
  -h, --help            show this help message and exit
  --all                 Fetch all Kaizo difficulty levels.
  --newcomer            Fetch Newcomer (diff_1) Kaizo hacks.
  --casual              Fetch Casual (diff_2) Kaizo hacks.
  --intermediate        Fetch Intermediate (diff_3) Kaizo hacks.
  --advanced            Fetch Advanced (diff_4) Kaizo hacks.
  --expert              Fetch Expert (diff_5) Kaizo hacks.
  --master              Fetch Master (diff_6) Kaizo hacks.
  --grandmaster         Fetch Grandmaster (diff_7) Kaizo hacks.
  --awaiting            Fetch hacks that are awaiting moderation.
  --base-dir BASE_DIR   Base directory where hacks will be saved (default: current directory).
  --clean-rom CLEAN_ROM
                        Path to a clean .smc file for patching (default: clean.smc).
  --flips FLIPS         Path to the flips executable (default: ./flips).

```

