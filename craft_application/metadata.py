from overrides import overrides
from pydantic_yaml import YamlModel


class MetadataModel(YamlModel):
    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic model configuration."""

        allow_population_by_field_name = True
        alias_generator = lambda s: s.replace("_", "-")  # noqa: E731

    @overrides
    def yaml(self) -> str:
        return super().yaml(
            by_alias=True,
            exclude_none=True,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
