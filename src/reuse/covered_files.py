# SPDX-FileCopyrightText: 2017 Free Software Foundation Europe e.V. <https://fsfe.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The REUSE Specification has a concept called Covered Files; files which must
contain licensing information. Some files in a project are not Covered Files,
and thus needn't contain licensing information. This module contains all that
logic.
"""

import contextlib
import logging
import os
from pathlib import Path
from typing import Collection, Generator, Optional, Set, cast

from . import (
    _IGNORE_DIR_PATTERNS,
    _IGNORE_FILE_PATTERNS,
    _IGNORE_MESON_PARENT_DIR_PATTERNS,
)
from ._util import StrPath, is_relative_to
from .vcs import VCSStrategy

_LOGGER = logging.getLogger(__name__)


def is_path_ignored(
    path: Path,
    subset_files: Optional[Collection[StrPath]] = None,
    include_submodules: bool = False,
    include_meson_subprojects: bool = False,
    vcs_strategy: Optional[VCSStrategy] = None,
) -> bool:
    """Is *path* ignored by some mechanism?"""
    # pylint: disable=too-many-return-statements,too-many-branches
    name = path.name
    parent_parts = path.parent.parts
    parent_dir = parent_parts[-1] if len(parent_parts) > 0 else ""

    if path.is_symlink():
        _LOGGER.debug("skipping symlink '%s'", path)
        return True

    if path.is_file():
        if subset_files is not None and path.resolve() not in subset_files:
            return True
        for pattern in _IGNORE_FILE_PATTERNS:
            if pattern.match(name):
                return True
        # Suppressing this error because I simply don't want to deal
        # with that here.
        with contextlib.suppress(OSError):
            if path.stat().st_size == 0:
                _LOGGER.debug("skipping 0-sized file '%s'", path)
                return True

    elif path.is_dir():
        if subset_files is not None and not any(
            is_relative_to(Path(file_), path.resolve())
            for file_ in subset_files
        ):
            return True
        for pattern in _IGNORE_DIR_PATTERNS:
            if pattern.match(name):
                return True
        if not include_meson_subprojects:
            for pattern in _IGNORE_MESON_PARENT_DIR_PATTERNS:
                if pattern.match(parent_dir):
                    _LOGGER.info(
                        "ignoring '%s' because it is a Meson subproject", path
                    )
                    return True
        if (
            not include_submodules
            and vcs_strategy
            and vcs_strategy.is_submodule(path)
        ):
            _LOGGER.info("ignoring '%s' because it is a submodule", path)
            return True

    if vcs_strategy and vcs_strategy.is_ignored(path):
        return True

    return False


def iter_files(
    directory: StrPath,
    subset_files: Optional[Collection[StrPath]] = None,
    include_submodules: bool = False,
    include_meson_subprojects: bool = False,
    vcs_strategy: Optional[VCSStrategy] = None,
) -> Generator[Path, None, None]:
    """Yield all Covered Files in *directory* and its subdirectories according
    to the REUSE Specification.
    """
    directory = Path(directory)
    if subset_files is not None:
        subset_files = cast(
            Set[Path], {Path(file_).resolve() for file_ in subset_files}
        )

    for root_str, dirs, files in os.walk(directory):
        root = Path(root_str)
        _LOGGER.debug("currently walking in '%s'", root)

        # Don't walk ignored directories
        for dir_ in list(dirs):
            the_dir = root / dir_
            if is_path_ignored(
                the_dir,
                subset_files=subset_files,
                include_submodules=include_submodules,
                include_meson_subprojects=include_meson_subprojects,
                vcs_strategy=vcs_strategy,
            ):
                _LOGGER.debug("ignoring '%s'", the_dir)
                dirs.remove(dir_)

        # Filter files.
        for file_ in files:
            the_file = root / file_
            if is_path_ignored(
                the_file,
                subset_files=subset_files,
                include_submodules=include_submodules,
                include_meson_subprojects=include_meson_subprojects,
                vcs_strategy=vcs_strategy,
            ):
                _LOGGER.debug("ignoring '%s'", the_file)
                continue

            _LOGGER.debug("yielding '%s'", the_file)
            yield the_file
