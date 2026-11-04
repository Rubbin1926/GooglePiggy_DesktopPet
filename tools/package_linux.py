"""Stage portable launchers, licenses, update manifest and a reproducible file list."""
import ast
import json
from pathlib import Path
import shutil
import sys
import tarfile
import subprocess

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
    preview = root/'docs/linux-preview.png'
    if preview.is_file():
        (folder/'docs').mkdir(exist_ok=True)
        shutil.copy2(preview, folder/'docs/linux-preview.png')
    if (folder/'_internal/licenses').is_dir():
        shutil.copytree(folder/'_internal/licenses', folder/'licenses', dirs_exist_ok=True)
    if (root/'licenses').is_dir():
        shutil.copytree(root/'licenses', folder/'licenses', dirs_exist_ok=True)
    # Keep the copyright statements for the actual Ubuntu library inputs.
    stack = [ast.literal_eval((root/'build/linux_pet/Analysis-00.toc').read_text())]
    system_paths = set()
    while stack:
        item = stack.pop()
        if isinstance(item, (tuple, list)):
            if len(item) == 3 and isinstance(item[1], str) and item[1].startswith(('/lib/', '/usr/lib/')) and item[2] in ('BINARY', 'EXTENSION'):
                path = item[1]
                system_paths.update((path, path[4:] if path.startswith('/usr/lib/') else '/usr'+path))
            else:
                stack.extend(item)
    result = subprocess.run(['dpkg-query', '-S', *sorted(system_paths)], capture_output=True, text=True)
    packages = {line.partition(': ')[0].split(':')[0] for line in result.stdout.splitlines() if ': ' in line}
    for package in sorted(packages):
        copyright = Path('/usr/share/doc')/package/'copyright'
        if copyright.is_file():
            target = folder/'licenses/Ubuntu'/package
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copyright, target/'copyright')
    shutil.copytree('/usr/share/common-licenses', folder/'licenses/Ubuntu/common-licenses', dirs_exist_ok=True)
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
