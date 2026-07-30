from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetBase(BaseModel):
    name: str = Field(..., example="sales_data")
    n_columns: int = Field(..., example=5)
    n_rows: int = Field(..., example=10000)
    column_types: dict[str, str] = Field(
        ..., example={"price": "float", "date": "datetime", "category": "string"}
    )


class DatasetCreate(DatasetBase):
    pass


class Dataset(DatasetBase):
    dataset_id: int
    created_at: datetime
    user_id: int
    model_config = ConfigDict(from_attributes=True)
