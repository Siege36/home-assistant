"""Helpers to download repository content."""
import pathlib
import tempfile
import zipfile
from custom_components.hacs.hacsbase.exceptions import HacsException
from custom_components.hacs.handler.download import async_download_file, async_save_file
from custom_components.hacs.helpers.filters import filter_content_return_one_of_type


async def download_zip(repository, validate):
    """Download ZIP archive from repository release."""
    contents = []
    try:
        for release in repository.releases.objects:
            repository.logger.info(
                f"ref: {repository.ref}  ---  tag: {release.tag_name}"
            )
            if release.tag_name == repository.ref.split("/")[1]:
                contents = release.assets

        if not contents:
            return validate

        for content in contents:
            filecontent = await async_download_file(
                repository.hass, content.download_url
            )

            if filecontent is None:
                validate.errors.append(f"[{content.name}] was not downloaded.")
                continue

            result = await async_save_file(
                f"{tempfile.gettempdir()}/{repository.repository_manifest.filename}",
                filecontent,
            )
            with zipfile.ZipFile(
                f"{tempfile.gettempdir()}/{repository.repository_manifest.filename}",
                "r",
            ) as zip_file:
                zip_file.extractall(repository.content.path.local)

            if result:
                repository.logger.info(f"download of {content.name} complete")
                continue
            validate.errors.append(f"[{content.name}] was not downloaded.")
    except Exception as exception:  # pylint: disable=broad-except
        validate.errors.append(f"Download was not complete [{exception}]")

    return validate


class contentObj:
    def __init__(self, url, path, name):
        self.download_url = url
        self.path = path
        self.name = name


async def download_content(repository, validate, local_directory):
    """Download the content of a directory."""
    contents = []
    try:
        if repository.releases.releases and repository.information.category in [
            "plugin",
            "theme",
        ]:
            for release in repository.releases.objects:
                if repository.status.selected_tag == release.tag_name:
                    for asset in release.assets:
                        contents.append(asset)
        if not contents:
            if repository.content.single:
                for repository_object in repository.content.objects:
                    contents.append(
                        contentObj(
                            repository_object.download_url,
                            repository_object.path,
                            repository_object.name,
                        )
                    )
            else:
                tree = repository.tree
                if repository.repository_manifest.content_in_root:
                    if repository.repository_manifest.filename is None:
                        if repository.information.category == "theme":
                            tree = filter_content_return_one_of_type(
                                repository.tree, "themes", "yaml", "full_path"
                            )
                for path in tree:
                    if path.is_directory:
                        continue
                    if path.full_path.startswith(repository.content.path.remote):
                        contents.append(
                            contentObj(path.download_url, path.full_path, path.filename)
                        )

        if not contents:
            raise HacsException("No content to download")

        for content in contents:
            if repository.repository_manifest.content_in_root:
                if repository.repository_manifest.filename is not None:
                    if content.name != repository.repository_manifest.filename:
                        continue
            repository.logger.debug(f"Downloading {content.name}")

            filecontent = await async_download_file(
                repository.hass, content.download_url
            )

            if filecontent is None:
                validate.errors.append(f"[{content.name}] was not downloaded.")
                continue

            # Save the content of the file.
            if repository.content.single or content.path is None:
                local_directory = repository.content.path.local

            else:
                _content_path = content.path
                if not repository.repository_manifest.content_in_root:
                    _content_path = _content_path.replace(
                        f"{repository.content.path.remote}", ""
                    )

                local_directory = f"{repository.content.path.local}/{_content_path}"
                local_directory = local_directory.split("/")
                del local_directory[-1]
                local_directory = "/".join(local_directory)

            # Check local directory
            pathlib.Path(local_directory).mkdir(parents=True, exist_ok=True)

            local_file_path = f"{local_directory}/{content.name}"
            result = await async_save_file(local_file_path, filecontent)
            if result:
                repository.logger.info(f"download of {content.name} complete")
                continue
            validate.errors.append(f"[{content.name}] was not downloaded.")

    except Exception as exception:  # pylint: disable=broad-except
        validate.errors.append(f"Download was not complete [{exception}]")
    return validate
