# Container recipe to reproject images from Posttroll messages

This recipe is automatically built on new version tags, and the image
is available from
https://quay.io/repository/fmi/weather-satellites-gdal-warper

## Configuration

The configuration files should be mounted to `/config/` directory. The
input directory needs to be mounted to match the locations in the
incoming Posttroll messages. Similarly output directory need to match
the path expected by the next processing steps.

### `/config/env-variables`

This file is used to set optional environment variables. The file
needs to exist even if no environment variables are set.
