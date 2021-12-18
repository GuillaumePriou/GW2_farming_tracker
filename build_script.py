import argparse
import logging
import os
import platform
import shutil
from importlib import metadata
from pathlib import Path
from typing import Any

from PyInstaller import __main__, compat

LOGGER = logging.getLogger("PyInstaller wrapper")


class WrapperFormatter(
    argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter
):
    """Class to merge two functionalities"""


def clean(distpath: Path, name: str):
    """
    Clean target bundle directory and files.

    Args:
        distpath: Path to the distribution directory
        name: Name of the executable and directory to bundle to

    Raises:
        RuntimeError: some file or directory couldn't be cleared
    """
    LOGGER.info("cleaning build targets...")
    bundle = distpath / name
    LOGGER.info("checking for %s", bundle)
    if bundle.exists():
        LOGGER.info("deleting %s", bundle)
        if bundle.is_file():
            bundle.unlink()
        elif bundle.is_dir():
            shutil.rmtree(bundle)
        else:
            raise RuntimeError(f"Could not delete {bundle}")

    zipfile = bundle.with_name(bundle.name + ".zip")
    LOGGER.info("checking for %s", zipfile)
    if zipfile.exists():
        LOGGER.info("deleting %s", zipfile)
        if zipfile.is_file():
            zipfile.unlink()
        elif zipfile.is_dir():
            shutil.rmtree(zipfile)
        else:
            raise RuntimeError(f"Could not delete {zipfile}")
    LOGGER.info("cone cleaning")


def bundle(distpath: Path, name: str, args: list[str], main: Path):
    """
    [Bundle the package using PyInstaller

    Args:
        distpath: PyInstaller's distpath argument
        name ([type]): PyInstaller's positional argument
        args ([type]): Additional PyInstaller args
        main ([type]): Path to the package entry-point
    """
    LOGGER.info("bundling %s to %s with PyInstaller...", main, name)
    args = ["--distpath", str(distpath), "--name", str(name), *args, str(main)]
    print(args)
    __main__.run(args)
    LOGGER.info("Done bundling %s", name)


def zip(distpath: Path, name: str):
    """
    Zip the resulting bundle dir into a zip file

    Args:
        distpath: distribution path used by PyInstaller
        name: name of the executable, directory and zip to produce
    """
    bundle = distpath / name
    LOGGER.info("zipping %s to %s...", bundle, bundle.with_name(bundle.name + ".zip"))
    shutil.make_archive(str(bundle), "zip", root_dir=str(bundle))
    LOGGER.info("done zipping")


def clean_post():
    """Cleans PyInstaller temporary files"""
    LOGGER.info("cleaning up pyinstaller files...")
    for file in Path.cwd().glob("*.spec"):
        file.unlink()
    LOGGER.info("done cleaning")


def main(package: Path, main: Path, distpath: Path, args: list[str]):
    """
    Bundle the app to target directory and zip file.

    The app name is formatted with the version and plateform to allow bundling
    on any platform. Previous folders and/or zip files of the same name are
    cleared before execution.

    Args:
        name: name of the executable and zip file to bundle the app in. The
            string is formatted using `str.format` with 'version' being the app
            version and 'plateform' the current platform.
        distpath: Path to the distribution directory
        remainder: Additional arguments to PyInstaller
    """
    logging.basicConfig(level=logging.INFO)

    app_name = package.name
    version = metadata.version(package.name)
    system = platform.system().lower()
    name = f"{app_name}-{version}-{system}"
    LOGGER.info("building %s from %s", name, package)

    clean(distpath, name)
    bundle(distpath, name, args, main)
    zip(distpath, name)
    clean_post()

    LOGGER.info("done building %s", name)


def check_arguments(
    parser: argparse.ArgumentParser, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """
    Check and format arguments to the main function

    Args:
        parser: parser used to parse the arguments
        kwargs: arguments to check

    Returns:
        kwargs: Cleaned arguments
    """
    # Check the compiled package was correctly specified
    package: Path = kwargs["package"]
    if not package.is_dir():
        parser.error(f"{package} is not a directory")

    main = package / kwargs["main"]
    if not main.is_file():
        parser.error(f"{main} is not a file")
    if not main.suffix == ".py":
        parser.error(f"{main} is not a python file")
    kwargs["main"] = main

    # Convert --add-data to plateform specific syntax
    add_data = [
        part
        for data in kwargs.pop("add_data")
        for part in ["--add-data", os.pathsep.join(data.split(":"))]
    ]

    # Rename additional args, adds data
    kwargs["args"] = kwargs.pop("...") + add_data

    return kwargs


if __name__ == "__main__":
    # Build our wrapper
    parser = argparse.ArgumentParser(
        prog="PyInstaller_wrapper",
        description=(
            "Wrapper around PyInstaller CLI to get platform and version number"
        ),
        formatter_class=WrapperFormatter,
    )
    novel_group = parser.add_argument_group(
        title="Package arguments",
        description=(
            "Package to bundle and its entrypoint. Used to build PyInstaller's "
            "positional argument and --name argument. The name of the executable "
            "to build is '{package}-{version}-{plateform}{extension}'. If the "
            "platform is windows, the extension is '.exe', otherwise nothing."
        ),
    )
    novel_group.add_argument(
        "package",
        type=Path,
        help=(
            "Path to the root directory of the package to bundle. The directory "
            "should have the same name as the package, and this name is used to "
            "retrieve version information using 'importlib.metadata'."
        ),
    )
    novel_group.add_argument(
        "-m",
        "--main",
        default="__main__.py",
        help=(
            "Path to the entry-point module of the bundled package. This is "
            "appended to the 'package' path."
        ),
    )

    pyinstaller_group = parser.add_argument_group(title="PyInstaller wrapped arguments")
    # Catch arguments of PyInstaller we are interested in
    pyinstaller_group.add_argument(
        "--distpath",
        type=Path,
        required=True,
        help=(
            "See --distpath from PyInstaller below. Must be catched by this "
            "wrapper for zipping the resulting directory."
        ),
    )
    pyinstaller_group.add_argument(
        "--add-data",
        action="append",
        default=[],
        metavar="<SRC:DEST>",
        help=(
            "See --add-data from PyInstaller's help message below. This argument"
            "must be provided with a ':' separator. This script will convert it"
            "to plateform-specific format and pass it to pyinstaller. This allows"
            "for a unified syntax which can be called on all plateforms"
        ),
    )
    # Catch all remaining args
    pyinstaller_group.add_argument(
        "...",
        nargs=argparse.REMAINDER,
        help="Additional arguments to PyInstaller",
    )

    # Add PyInstaller own help message at the end to provide complete doc
    try:
        compat.check_requirements()
    except Exception as err:
        parser.error(f"PyInstaller is missing dependencies: {err}")
    pyinstaller_parser = __main__.generate_parser()
    parser.epilog = "PyInstaller arguments:\n" "+---------------------\n" "|\n| "
    parser.epilog += pyinstaller_parser.format_help().replace("\n", "\n| ")
    parser.epilog += (
        "\n+---------------------\n"
        "\n"
        "See above for the wrapper script own arguments."
    )

    # Parse args and run
    kwargs = vars(parser.parse_args())
    main(**check_arguments(parser, kwargs))
