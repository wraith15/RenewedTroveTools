import argparse
import subprocess
import sys
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

from models.metadata import Metadata


def find_iscc() -> str:
    compiler = which("iscc") or which("ISCC")
    if compiler:
        return compiler

    program_files = [
        Path(r"C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path(r"C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for candidate in program_files:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH."
    )


def find_build_output() -> Path:
    build_dirs = [path for path in Path("build").glob("exe.*") if path.is_dir()]
    if not build_dirs:
        raise FileNotFoundError("No cx_Freeze build output found under build/.")
    return max(build_dirs, key=lambda path: path.stat().st_mtime)


def create_iss_contents(metadata: Metadata, build_dir: Path, output_name: str, debug: bool) -> str:
    app_id = metadata.app_id.strip("{}")
    app_name = metadata.name + (" Debug" if debug else "")
    repo_url = f"https://github.com/{metadata.resolved_github_repo}"
    build_dir_windows = str(build_dir.resolve()).replace("/", "\\")
    output_dir_windows = str(Path("dist").resolve()).replace("/", "\\")
    icon_path = str(Path("assets/x256.ico").resolve()).replace("/", "\\")
    installer_name = output_name.replace("-", " ")

    return f'''[Setup]
AppId={{{{{app_id}}}
AppName={app_name}
AppVersion={metadata.version}
AppVerName={app_name} {metadata.version}
AppPublisher={metadata.author}
AppPublisherURL={repo_url}
AppSupportURL={repo_url}
AppUpdatesURL={repo_url}/releases/latest
DefaultDirName={{autopf}}\\{metadata.tech_name}
DefaultGroupName={metadata.name}
DisableProgramGroupPage=yes
DirExistsWarning=no
UninstallDisplayIcon={{app}}\\{metadata.tech_name}.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir={output_dir_windows}
OutputBaseFilename={output_name}
SetupIconFile={icon_path}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={metadata.version}
VersionInfoCompany={metadata.author}
VersionInfoDescription={installer_name}
VersionInfoProductName={metadata.name}
SetupLogging=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{build_dir_windows}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{metadata.name}"; Filename: "{{app}}\\{metadata.tech_name}.exe"
Name: "{{autodesktop}}\\{metadata.name}"; Filename: "{{app}}\\{metadata.tech_name}.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{metadata.tech_name}.exe"; Description: "Launch {metadata.name}"; Flags: nowait postinstall skipifsilent
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Windows installer with Inno Setup.")
    parser.add_argument("--debug", action="store_true", help="Build the debug installer.")
    args = parser.parse_args()

    metadata = Metadata.load_from_file(Path("data/metadata.json"))
    compile_script = "compile-debug.py" if args.debug else "compile.py"
    output_name = (
        f"{metadata.tech_name}-{metadata.version}-win64-debug-setup"
        if args.debug
        else f"{metadata.tech_name}-{metadata.version}-win64-setup"
    )

    subprocess.run([sys.executable, compile_script, "build_exe"], check=True)
    build_dir = find_build_output()
    Path("dist").mkdir(exist_ok=True)
    iscc = find_iscc()

    with TemporaryDirectory() as temp_dir:
        iss_path = Path(temp_dir) / "installer.iss"
        iss_path.write_text(
            create_iss_contents(metadata, build_dir, output_name, args.debug),
            encoding="utf-8",
        )
        subprocess.run([iscc, str(iss_path)], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())