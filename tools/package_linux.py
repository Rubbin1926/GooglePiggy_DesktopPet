"""Package the Linux app without an interpreter; setup uses Ubuntu's Python."""
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
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    files = set(root.glob('*.py')) | set((root/'linux').glob('*.py'))
    for directory in ('assets/macos-resources', 'licenses'):
        files.update(path for path in (root/directory).rglob('*') if path.is_file())
    files.update(root/name for name in (
        'setup-linux.sh', 'start-linux.sh', 'install-linux.sh', 'uninstall-linux.sh',
        'install-deps-linux.sh', 'build-linux.sh', 'tools/package_linux.py',
        'requirements.txt', 'requirements-linux.txt',
        'requirements-linux.lock', 'requirements-linux-apt.txt', 'README-LINUX.md',
        'LINUX-PORTING.md', 'THIRD-PARTY-LINUX.md', 'LICENSE', 'ASSET-NOTICE.md', 'docs/linux-preview.png'))
    for path in sorted(files):
        target = folder/path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    shutil.copy2(folder/'start-linux.sh', folder/'googlepiggy')
    for path in [folder/'googlepiggy', *folder.glob('*.sh')]:
        path.chmod(0o755)
    checksums = {str(path.relative_to(folder)): digest(path)
                 for path in sorted(folder.rglob('*')) if path.is_file()}
    (folder/MANIFEST).write_text(json.dumps({
        'schema': 1, 'platform': 'linux-x86_64', 'version': VERSION,
        'runtime': 'system-python', 'files': checksums}, indent=2)+'\n')
    validate_tree(folder, VERSION)
    archive = root/'dist'/f'GooglePiggy-{VERSION}-linux-x86_64.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=True) as stream:
        for child in sorted(folder.iterdir()):
            stream.add(child, arcname=child.name)
    (archive.parent/'SHA256SUMS.txt').write_text(digest(archive)+'  '+archive.name+'\n')
    print(json.dumps({'archive': str(archive), 'files': len(checksums), 'sha256': digest(archive)}))


if __name__ == '__main__':
    main()
