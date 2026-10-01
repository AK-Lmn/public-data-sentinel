# Data quality: FAIL

Records checked: 3
Issues: 5

| Record | Field | Code | Detail |
| --- | --- | --- | --- |
| 1 | rainfall_mm | minimum | Value is outside minimum 0 |
| 2 | rainfall_mm | type | Number must be finite |
| 2 | quality | enum | Value is not in the allowed list |
| 2 | station_id, date | duplicate | Key duplicates record 1 |
| 3 | date | type | Date does not exist |
