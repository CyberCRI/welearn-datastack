import logging
import os
from pathlib import Path
from typing import Tuple

from welearn_datastack.data.enumerations import MLModelsType

logger = logging.getLogger(__name__)


def setup_local_path() -> Tuple[Path, Path]:
    """
    Setup local path for input and output artifacts for a given node
    :return: Tuple of local path for input and output artifacts
    """
    artifact_root: str | None = os.environ.get("ARTIFACT_ROOT")
    input_name: str = os.environ.get("ARTIFACT_INPUT_FOLDER_NAME", "input")
    output_name: str = os.environ.get("ARTIFACT_OUTPUT_FOLDER_NAME", "output")

    if artifact_root is None:
        raise ValueError("ARTIFACT_ROOT is not defined")
    local_artifcat_root: Path = Path(artifact_root)
    logger.info("Local artifact root: %s", local_artifcat_root)
    logger.info(
        "Local artifact root exists: %s and it's folder : %s",
        local_artifcat_root.exists(),
        local_artifcat_root.is_dir(),
    )

    local_artifcat_input: Path = local_artifcat_root / input_name
    logger.info("Local artifact input: %s", local_artifcat_input)

    local_artifcat_output: Path = local_artifcat_root / output_name
    logger.info("Local artifact output: %s", local_artifcat_output)

    logger.info(
        "Local artifact output exists: %s and it's folder : %s, it's file: %s",
        local_artifcat_output.exists(),
        local_artifcat_output.is_dir(),
        local_artifcat_output.is_file(),
    )
    logger.info(
        "Local artifact input exists: %s and it's folder : %s, it's file: %s",
        local_artifcat_input.exists(),
        local_artifcat_input.is_dir(),
        local_artifcat_input.is_file(),
    )

    local_artifcat_input.mkdir(parents=True, exist_ok=True)
    local_artifcat_output.mkdir(parents=True, exist_ok=True)

    return local_artifcat_input, local_artifcat_output


def generate_ml_models_path(
    model_type: MLModelsType,
    model_name: str,
    extension: str = "joblib",
    folder: bool = False,
) -> Path:
    """
    Generate the path of a model according to the type and the name
    :param folder: If the path is a folder
    :param model_type: The type of the model
    :param model_name: The name of the model
    :param extension: The extension of the model
    :return: The path of the model
    """
    model_path_root: str | None = os.environ.get("MODELS_PATH_ROOT")
    if model_path_root is None:
        raise ValueError("MODELS_PATH_ROOT is not defined")

    prefix_path = Path(model_path_root) / Path(model_type.name.lower())
    if folder:
        return prefix_path / Path(model_name)

    if not model_name.endswith(extension):
        file_name = Path(f"{model_name}.{extension}")
    else:
        file_name = Path(model_name)

    return prefix_path / file_name
