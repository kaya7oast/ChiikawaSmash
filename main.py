"""Chiikawa Smash - a tiny Smash-style platform fighter.

PC:            python main.py          (needs:  pip install pygame)
Web / phone:   built by GitHub Actions with pygbag (see README)
"""
import asyncio

import pygame  # noqa: F401  (pygbag scans main.py's imports to know it must package pygame)

from smash.app import main

asyncio.run(main())
