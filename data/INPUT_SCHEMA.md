# Logical Input Schema

Data kind: **image**

Required logical fields:

- `product_id`
- `science_array`
- `uncertainty_array`
- `dq_mask`
- `wcs_or_detector_geometry`
- `exposure_metadata`
- `calibration_reference_ids`

Map archive-specific names to these logical fields in a versioned configuration file. Fail clearly when a required field is absent.
