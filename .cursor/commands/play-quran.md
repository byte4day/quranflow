# Play Qur'an with QuranFlow

Run exactly one command and reply with its single output line:

`python3 ~/.agents/skills/play-quran/scripts/play_quran.py --brief <arguments after /play-quran>`

Pass the arguments as separate words (`yasin`, `36`, `--reciter dosari`, `pause`,
`resume`, `stop`, `status`, `volume 40`). With no arguments, the remembered Surah and
reciter play. Do not run `status` or list catalogs first. Report errors in one sentence.
If the helper is missing, tell the user to run `./install.sh` in the QuranFlow checkout.
