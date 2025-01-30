import copy
import numpy
from collada import *
from numpy.random import Generator
from randomgen import ChaCha
import os, sys
from PIL import Image, ImageDraw, ImageFilter

#FIXME: remove base of scan. It's not part of the object being fractionalized...

TRICOUNT = 9

os.makedirs("dest/textures", exist_ok=True)

RND = Generator(ChaCha(0xf22b988a9083377, rounds=8))

def subset_image(image, uvs):
    im = Image.new("RGB", image.size)
    mask = Image.new('1', image.size)
    d = ImageDraw.Draw(mask)
    # Extract x and y coordinates
    x_indices = [x for x in range(0, len(uvs), 2)]
    y_indices = [x for x in range(1, len(uvs), 2)]
    xw = [round(uvs[x] * image.width) for x in x_indices]
    yh = [round((1.0 - uvs[y]) * image.height) for y in y_indices]
    # For each triangle's co-ordinates
    for i in range(0, len(x_indices), 3):
        offset = i
        # Stroke to Avoid dark jaggies at the edge
        d.polygon(
            [(xw[offset], yh[offset]),
             (xw[offset + 1], yh[offset + 1]),
             (xw[offset + 2], yh[offset + 2])],
            fill=255,
            stroke=255,
            width=3)
    im.paste(image, mask=mask)
    return im

def save_texture_images(images, uvs, i):
    filenames = {}
    j = 1
    for image in images.keys():
        im = subset_image(images[image], uvs)
        filename = f"textures/fragment-{i:03}{j:03}.jpg"
        with open(f"dest/{filename}", "wb") as f:
            im.save(f, quality="high")
        filenames[image] = filename
        j = j + 1
    return filenames

inmesh = Collada("src/1k.dae")
imimgs = {f"textures/{f}": Image.open(f"src/textures/{f}") for f in os.listdir("src/textures")}
# Nothing clever, we list the indices in order, even if the values are duplicated
indices = numpy.array([x for x in range(TRICOUNT * 3)])
ts = list(list(list(inmesh.scene.objects("geometry"))[0].primitives())[0].triangleset().triangles())

number = 1
while len(ts) > TRICOUNT * 3:
    print(f"{number} ", end = "", flush=True)
    mesh = copy.deepcopy(inmesh)

    triangles = ts[:TRICOUNT]
    ts = ts[TRICOUNT:]

    # There may be duplicates, we don't mind as we only have a few triangles.
    xyz = numpy.concatenate([t.vertices for t in triangles]).flatten()
    uv = numpy.concatenate([t.texcoords for t in triangles]).flatten()

    vert_src = source.FloatSource("xyz", numpy.array(xyz), ('X', 'Y', 'Z'))
    tex_src = source.FloatSource("uv", numpy.array(uv), ('S', 'T'))
    input_list = source.InputList()
    input_list.addInput(0, 'VERTEX', "#xyz")
    input_list.addInput(0, 'TEXCOORD', "#uv")

    geom = geometry.Geometry(mesh, "mesh_0", "", [vert_src, tex_src])
    triset = geom.createTriangleSet(indices, input_list, "materialref")
    geom.primitives.append(triset)
    mesh.geometries.append(geom)
    # Remove the source
    del mesh.geometries[0]

    imgs = save_texture_images(imimgs, uv, number)
    for img in mesh.images:
        if img.path in imgs.keys():
            img.path = imgs[img.path]
            img.save()

    # Regenerate the xml
    mesh.save()

    mesh.write(f"dest/fragment-{number}.dae")
    number += 1
    break

print()