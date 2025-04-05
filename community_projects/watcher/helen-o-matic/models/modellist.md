# Available Helen-O-Matic HEF Models

The following HEF (Hailo Executable Format) models are available in this directory:

## Model Details

### helen-o-matic.v5.yolov8
The v5 model is the first model trained on helen_out and helen_back, trained over 50 epochs. The first HEF conversion of this model did not appear to detect any objects. However, redoing the conversion process using --performance (see below) seems to fix this.
Data up to 23/03/25.

### helen-o-matic.v5.yolov8
The v5p model seems to work to some degree. Detecting helen_out and helen_back seems reasonable but there is a propensity to recognise too many dogs (car tyres, children etc).
Data up to 23/03/25.

### helen-o-matic.v6.yolov8 and helen-o-matic.v6p.yolov8
The v6 model is trained with added augmentations and 150 epochs. It seems to be much better at rejecting false positives for dogs. The p suffix is for --performance.
Data up to 23/03/25.

### helen-o-matic.v7.yolov8 and ### helen-o-matic.v7p.yolov8
The v7 model is trained with more images of children, people and dogs.
Data up to 04/04/25.