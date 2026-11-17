"""Independent Linux release channel, verified downloads and bounded extraction."""
import hashlib
import json
import queue
import re
import shutil
import tarfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

from linux import REPOSITORY
from linux.paths import app_root, read_json

WEB = 'https://github.com/'+REPOSITORY+'/releases/'
API = 'https://api.github.com/repos/'+REPOSITORY+'/releases'
MANIFEST = 'linux-update.json'
MANIFEST_CHECKSUM = f'# {MANIFEST} SHA-256 '
MAX_PACKAGE = 512*1024*1024
MAX_EXPANDED = 1536*1024*1024


def version(number):
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', number):
        raise ValueError('无效的 Linux 版本号')
    values = tuple(map(int, number.split('.')))
    return values+(0,)*(4-len(values))


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    url: str
    asset_url: str
    size: int
    digest: str


@dataclass(frozen=True)
class UpdateCheck:
    release: Release | None = None
    message: str = ''


def linux_release_rows(rows, include_prerelease):
    for row in rows:
        if not isinstance(row, dict) or row.get('draft') is not False:
            continue
        preview = row.get('prerelease')
        if preview is not False and not (include_prerelease and preview is True):
            continue
        tag = row.get('tag_name', '')
        match = re.fullmatch(r'v(\d+(?:\.\d+){1,3})-linux', tag) if isinstance(tag, str) else None
        if match and row.get('html_url') == WEB+'tag/'+tag:
            yield match[1], row


def release_asset(row, filename, limit):
    assets = row.get('assets')
    if not isinstance(assets, list):
        return None
    url = WEB+'download/'+row['tag_name']+'/'+filename
    matches = [a for a in assets if isinstance(a, dict) and a.get('name') == filename and
               a.get('browser_download_url') == url and a.get('state', 'uploaded') == 'uploaded' and
               type(a.get('size')) is int and 0 < a['size'] <= limit and
               re.fullmatch(r'sha256:[a-f0-9]{64}', str(a.get('digest', '')))]
    return matches[0] if len(matches) == 1 else None


def parse_releases(rows, include_prerelease=False):
    releases = []
    for number, row in linux_release_rows(rows, include_prerelease):
        filename = f'GooglePiggy-{number}-linux-x86_64.tar.gz'
        a = release_asset(row, filename, MAX_PACKAGE)
        if not a:
            continue
        notes = '\n'.join(line.strip()[2:] for line in str(row.get('body', '')).splitlines()
                          if line.strip().startswith(('- ', '* ')))[:180]
        releases.append(Release(number, notes or '新版已发布，可下载更新。', row['html_url'], a['browser_download_url'], a['size'], a['digest']))
    return releases


def published_manifest_digest(release, row):
    asset = release_asset(row, 'SHA256SUMS.txt', 4096)
    if not asset:
        return None
    request = Request(asset['browser_download_url'], headers={'User-Agent': 'GooglePiggy-Linux', 'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=15) as response:
        data = response.read(asset['size']+1)
    if len(data) != asset['size'] or 'sha256:'+hashlib.sha256(data).hexdigest() != asset['digest']:
        raise ValueError('发布校验文件的 SHA-256 不匹配')
    lines = data.decode('ascii').splitlines()
    filename = PurePosixPath(release.asset_url).name
    if f'{release.digest.removeprefix("sha256:")}  {filename}' not in lines:
        raise ValueError('发布校验文件与安装包不匹配')
    checksums = [line.removeprefix(MANIFEST_CHECKSUM) for line in lines if line.startswith(MANIFEST_CHECKSUM)]
    if not checksums:
        return None
    if len(checksums) != 1 or not re.fullmatch(r'[a-f0-9]{64}', checksums[0]):
        raise ValueError('无效的安装清单校验值')
    return checksums[0]


def check_releases(current, *, manual=False, root=None):
    releases = []
    for page in range(1, 6):
        request = Request(API+f'?per_page=100&page={page}', headers={
            'User-Agent': 'GooglePiggy-Linux', 'Accept': 'application/vnd.github+json', 'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=15) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError('更新响应过大')
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError('无效的更新响应')
        releases.extend(rows)
        if len(rows) < 100:
            break
    else:
        raise ValueError('更新列表分页未完成')
    latest = max(linux_release_rows(releases, manual), key=lambda item: version(item[0]), default=None)
    if latest is None:
        return UpdateCheck(message='未找到公开的 Linux 发布')
    number, row = latest
    usable = parse_releases([row], include_prerelease=manual)
    if not usable:
        return UpdateCheck(message='Linux 发布包暂不可验证')
    release = usable[0]
    published, local_version = version(number), version(current)
    if published > local_version:
        return UpdateCheck(release)
    if not manual or published < local_version:
        return UpdateCheck(message='当前版本高于最新发布' if manual else '')

    installed = Path(root) if root is not None else app_root()
    local = installed/MANIFEST
    if local.is_file():
        expected = published_manifest_digest(release, row)
        if expected:
            if digest(local) != expected:
                return UpdateCheck(release, '同版本的发布包与本机不同')
            try:
                validate_tree(installed, number, installed=True)
            except (OSError, ValueError):
                return UpdateCheck(message='无法核对当前安装包')
            return UpdateCheck(message='当前安装包已是最新')
    return UpdateCheck(message='版本相同，安装包待核对')


def safe_path(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or '..' in p.parts or ':' in name:
        raise ValueError('更新包包含不安全的路径')
    return p


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def validate_tree(root, expected, *, installed=False):
    root = Path(root)
    manifest = read_json(root/MANIFEST) or {}
    if not isinstance(manifest, dict) or manifest.get('schema') != 1 or manifest.get('platform') != 'linux-x86_64' or manifest.get('version') != expected:
        raise ValueError('更新包的平台或版本不匹配')
    files = manifest.get('files')
    if not isinstance(files, dict) or 'googlepiggy' not in files:
        raise ValueError('更新包缺少程序或文件清单')
    if not installed:
        # Installed copies can also contain the virtual environment created by setup.
        entries = list(root.rglob('*'))
        if any(p.is_symlink() for p in entries):
            raise ValueError('更新包包含符号链接')
        actual = {str(p.relative_to(root)) for p in entries if p.is_file() and p != root/MANIFEST}
        if actual != set(files):
            raise ValueError('更新包文件清单不一致')
    for name, expected_digest in files.items():
        p = root.joinpath(*safe_path(name).parts)
        if p.is_symlink() or not re.fullmatch(r'[a-f0-9]{64}', str(expected_digest)) or digest(p) != expected_digest:
            raise ValueError('更新包文件校验失败：'+name)
    if not (root/'googlepiggy').stat().st_mode & 0o111:
        raise ValueError('更新包程序没有执行权限')
    return manifest


def extract_package(archive, destination, expected):
    destination = Path(destination)
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers()
        if len(members) > 50_000 or sum(m.size for m in members) > MAX_EXPANDED:
            raise ValueError('更新包超过展开限制')
        names = set()
        for member in members:
            path = safe_path(member.name)
            if str(path) in names or not (member.isfile() or member.isdir()):
                raise ValueError('更新包包含重复路径、链接或特殊文件')
            names.add(str(path))
        for member in members:
            p = destination.joinpath(*safe_path(member.name).parts)
            if member.isdir():
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as source, p.open('xb') as target:
                    while chunk := source.read(1024*1024):
                        target.write(chunk)
                p.chmod(0o755 if member.mode & 0o111 else 0o644)
    validate_tree(destination, expected)
    return destination


class Updater:
    def __init__(self, current, directory):
        self.current, self.directory = current, Path(directory)
        self.results = queue.Queue()
        self.checking = self.manual = self.downloading = False
        self.cancel = threading.Event()

    def check(self, manual=False):
        self.manual |= manual
        if self.checking:
            return
        self.checking = True
        kind = 'manual-check' if manual else 'check'
        def work():
            try:
                self.results.put((kind, check_releases(self.current, manual=manual), None))
            except Exception as error:
                self.results.put((kind, None, str(error)))
        threading.Thread(target=work, daemon=True).start()

    def download(self, release):
        if self.downloading:
            return
        self.downloading = True
        self.cancel.clear()
        def work():
            archive = stage = None
            try:
                stage = self.directory/('update-'+uuid.uuid4().hex)
                stage.mkdir(parents=True, exist_ok=False)
                archive = stage/'download.tar.gz'
                total, checksum = 0, hashlib.sha256()
                req = Request(release.asset_url, headers={'User-Agent': 'GooglePiggy-Linux'})
                with urlopen(req, timeout=30) as response, archive.open('xb') as target:
                    while chunk := response.read(256*1024):
                        if self.cancel.is_set():
                            raise InterruptedError('下载已取消')
                        total += len(chunk)
                        if total > release.size or total > MAX_PACKAGE:
                            raise ValueError('更新下载超过预期大小')
                        checksum.update(chunk)
                        target.write(chunk)
                        self.results.put(('progress', total/release.size, None))
                if total != release.size or 'sha256:'+checksum.hexdigest() != release.digest:
                    raise ValueError('更新包 SHA-256 校验失败')
                self.results.put(('verifying', None, None))
                package = extract_package(archive, stage/'package', release.version)
                self.results.put(('ready', package, None))
            except Exception as error:
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)
                self.results.put(('failed', None, str(error)))
            finally:
                if archive:
                    archive.unlink(missing_ok=True)
                self.downloading = False
        threading.Thread(target=work, daemon=True).start()
