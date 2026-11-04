"""Stage portable launchers, licenses, update manifest and a reproducible file list."""
import json
from pathlib import Path
import shutil
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linux import VERSION
from linux.update import MANIFEST, digest, validate_tree


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root/'dist/GooglePiggy'
    if not (folder/'googlepiggy').is_file():
        raise SystemExit('先使用 linux_pet.spec 构建程序。')
    # PyInstaller creates internal library symlinks. Ship ordinary files so the
    # updater can reject every archive link, without weakening extraction checks.
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            target = path.resolve()
            if not target.is_relative_to(folder.resolve()) or not target.is_file():
                raise ValueError('Unexpected external/directory symlink: '+str(path))
            path.unlink()
            shutil.copy2(target, path)
    for name in ('start-linux.sh', 'install-linux.sh', 'uninstall-linux.sh', 'README-LINUX.md',
                 'THIRD-PARTY-LINUX.md', 'LICENSE', 'ASSET-NOTICE.md'):
        shutil.copy2(root/name, folder/name)
    for script in folder.glob('*.sh'):
        script.chmod(0o755)
    if (folder/'_internal/licenses').is_dir():
        shutil.copytree(folder/'_internal/licenses', folder/'licenses', dirs_exist_ok=True)
    # Preserve the actual runtime license from the dedicated Python installation.
    python_license = Path(sys.base_prefix)/'lib/python3.11/LICENSE.txt'
    if python_license.is_file():
        target = folder/'licenses/CPython'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(python_license, target/'LICENSE.txt')
    files = {str(path.relative_to(folder)): digest(path) for path in sorted(folder.rglob('*'))
             if path.is_file() and path != folder/MANIFEST}
    (folder/MANIFEST).write_text(json.dumps({'schema': 1, 'platform': 'linux-x86_64', 'version': VERSION,
                               'upstream': '1f69e17ff28666e735ed3a9957deed00da508cbf', 'files': files}, indent=2)+'\n')
    validate_tree(folder, VERSION)
    archive = root/'dist'/f'GooglePiggy-{VERSION}-linux-x86_64.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=True) as output:
        for child in sorted(folder.iterdir()):
            output.add(child, arcname=child.name)
    (archive.parent/'SHA256SUMS.txt').write_text(digest(archive)+'  '+archive.name+'\n')
    print(json.dumps({'archive': str(archive), 'files': len(files), 'sha256': digest(archive)}))


if __name__ == '__main__':
    main()
