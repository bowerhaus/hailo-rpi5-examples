# Available Pigeonator HEF Models

The following HEF (Hailo Executable Format) models are available in this directory:

## Model Details

### Pigeonator-v1
Trained on original pigeon images from 2021. Used for initial testing with the Hailo DFC. Tried with no gpuand no performance flag options. Performamce seemed rather poor in the new camera setting of MK3.

### Pigeonator-MK3-B
The B models are single catgory models with a new training set based on images captured by the MK3 device in situ.

### pigeonator-mk3-b.v2
The v2 model works well at identifying pigeons but produced false positives for people and dogs walking in the area. It's possible this might be better than first though since it was later discovered that a much higher confidence level (than the original 0.3) could be used.

### pigeonator-mk3-b.v3
The v3 model has addition images with people and dogs that are classified as background in order to make the model more resilient against false positives. In use, the confidence level was upped from 0.4 to 0.8. This performs well for most intrusions and for pigeons at the front of the pond and on the lawn. Not so good in the shady areas at the back.