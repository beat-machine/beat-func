import typing as t

import pydantic as pd
from beatmachine.effect_registry import EffectRegistry

MAX_EFFECTS = 5


class SettingsSchema(pd.BaseModel):
    suggested_bpm: t.Optional[int] = pd.Field(gt=60, lt=300, default=None)
    drift: int = pd.Field(ge=0, lt=200, default=15)

    @property
    def max_bpm(self) -> int:
        if self.suggested_bpm is not None:
            return self.suggested_bpm + self.drift
        else:
            return 300

    @property
    def min_bpm(self) -> int:
        if self.suggested_bpm is not None:
            return self.suggested_bpm - self.drift
        else:
            return 60


class JobSchema(pd.BaseModel):
    settings: SettingsSchema = pd.Field(default_factory=SettingsSchema)

    # becomes t.List[Effect] after validation (weird)
    effects: t.List[t.Any] = pd.Field(min_items=1, max_items=MAX_EFFECTS)

    @pd.validator("effects", each_item=True)
    def instantiate_effects(cls, v):
        try:
            return EffectRegistry.load_effect(v)
        except ValueError as e:
            raise pd.ValidationError("Failed to load effect", v) from e


class UrlJobSchema(JobSchema):
    url: pd.AnyHttpUrl
