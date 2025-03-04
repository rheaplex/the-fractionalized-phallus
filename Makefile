# 900 x 1600
# 4320 x 7680
WIDTH = 4320
HEIGHT = 7680
MODEL_DIR = gltf
IMG_DIR = png

F3D = /Applications/f3d.app/Contents/MacOS/f3d

#  --background-color=1.0,1.0,1.0
F3D_ARGS = --no-background=true \
		--resolution=$(WIDTH),$(HEIGHT) \
		--command-script=f3d-commands.txt

GLBS = $(wildcard $(MODEL_DIR)/*.glb)
GLTFS = $(patsubst $(MODEL_DIR)/%.glb, $(MODEL_DIR)/%.gltf, $(GLBS))
PNGS = $(patsubst $(MODEL_DIR)/%.glb, $(IMG_DIR)/%.png, $(GLBS))

all: glbs gltfs pngs

glbs: process.py
	python3 process.py

$(MODEL_DIR)/%.gltf: $(MODEL_DIR)/%.glb
	gltf-import-export $<

gltfs: $(GLTFS) 

$(IMG_DIR)/%.png: $(MODEL_DIR)/%.glb
	$(F3D) $(F3D_ARGS) --output $@ --input $<

pngs: $(PNGS)

clean:
	rm -f $(MODEL_DIR)/*.glb $(IMG_DIR)/*.png
