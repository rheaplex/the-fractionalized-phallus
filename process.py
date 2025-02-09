
import os
import base64
import struct
import io
import math
from scipy.spatial.transform import Rotation as R
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.spatial.transform import Rotation as R
from PIL import Image, ImageDraw, ImageFilter
import pygltflib

TRICOUNT = 1166

# Rotate each fragment so it's best oriented to the viewer.
ROTATION = R.from_euler('y', 45.0, degrees=True)

ANIMATION_TIMES = np.array(
    [0, 1.0, 2.0, 3.0, 4.0],
    dtype=np.float32
    )

ANIMATION_VALUES = np.array([
    [0.0, 0.0, 0.0, 1.0 ],
    [0.0, 0.707, 0.0, 0.707],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.707, 0.0, -0.707],
    [0.0, 0.0, 0.0, 1.0]
], dtype=np.float32)

def subset_image(image, uvs):
    im = Image.new("RGB", image.size)
    mask = Image.new('1', image.size)
    d = ImageDraw.Draw(mask)
    # For each triangle's co-ordinates
    for offset in range(0, len(uvs), 3):
        # Stroke to Avoid dark jaggies at the edge
        d.polygon(
            [(int(uvs[offset][0] * image.width),
                int(uvs[offset][1] * image.height)),
            (int(uvs[offset + 1][0] * image.width),
                int(uvs[offset + 1][1] * image.height)),
            (int(uvs[offset + 2][0] * image.width),
                int(uvs[offset + 2][1] * image.height))],
            fill=255,
            outline=255,
            width=10)
    im.paste(image, mask=mask)
    jpeg = io.BytesIO()
    im.save(jpeg, format="jpeg", quality="high")
    b64 = base64.standard_b64encode(jpeg.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"

COMPONENT_TYPES = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}

def accessor_component_type(accessor):
    return np.dtype(COMPONENT_TYPES[accessor.componentType])

def get_bufferview_data(gltf, bufferViewIndex, byteOffset=0):
    bufferView = gltf.bufferViews[bufferViewIndex]
    buffer = gltf.buffers[bufferView.buffer]
    data = gltf.get_data_from_buffer_uri(buffer.uri)
    offset = bufferView.byteOffset + byteOffset
    return data[offset:]

def get_data(gltf, accessor):
    return get_bufferview_data(gltf, accessor.bufferView, accessor.byteOffset or 0)

def get_indices(gltf, accessor):
    data = get_data(gltf, accessor)
    coords = np.frombuffer(
        data,
        dtype=accessor_component_type(accessor),
        count=accessor.count
        )
    return coords

def get_xyz(gltf, accessor):
    data = get_data(gltf, accessor)
    raw = np.frombuffer(
        data,
        dtype=accessor_component_type(accessor).newbyteorder('<'),
        count=accessor.count * 3
        )
    xyz = raw.reshape(-1, 3, copy=True)
    # Base the model on the horizontal plane
    min = xyz.max(axis=0).tolist()
    max = xyz.min(axis=0).tolist()
    xyz[:, 1] = xyz[:, 1] - min[1]
    return xyz

def get_uv(gltf, accessor):
    data = get_data(gltf, accessor)
    coords = np.frombuffer(
        data,
        dtype=accessor_component_type(accessor).newbyteorder('<'),
        count=accessor.count * 2
        )
    return sliding_window_view(coords, window_shape = 2)[::2]

def get_image(gltf, index):
    img = gltf.images[index]
    if img.uri:
        b64 = img.uri[len("data:image/jpeg;base64,"):]
        data = base64.standard_b64decode(b64)
    else:
        data = get_bufferview_data(gltf, img.bufferView)
    return Image.open(io.BytesIO(data))

def center_fragment(xyz):
    return xyz - xyz.mean(axis=0)
    
def rotate_fragment(xyz):
    # This ends up as float64s
    rotated = ROTATION.apply(xyz)
    # Convert back to float32 for serialization later
    return np.float32(rotated)

def save_fragment(sourceIndices, sourceXYZ, sourceUV, sourceImage, number, start, count):
    indices = sourceIndices[range(start, start + count)]
    xyz = sourceXYZ[indices]
    xyz = center_fragment(xyz)
    xyz = rotate_fragment(xyz)
    uv = sourceUV[indices]
    img = subset_image(sourceImage, uv)
    xyz_binary_blob = xyz.flatten().tobytes()
    uv_binary_blob = uv.flatten().tobytes()
    #quat = Q[list(Q.keys())[number - 1]] #Quaternion(axis=[0, 1, 0], angle=YA_SWIZZLE[number - 1])
    #animation_binary_blob = np.array(ANIMATION_TIMES).flatten().tobytes() \
    #    + np.array(ANIMATION_VALUES).flatten().tobytes()
    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[0])],
        nodes=[pygltflib.Node(
            mesh=0,
            rotation=[0, 0, 0, 1],
            translation=[ 0.0, 0.0, 0.0 ],
            scale=[ 1.0, 1.0, 1.0 ],
            name="Y_UP"
        )],
        # pygltflib.Node(
        #     camera=0,
        #     translation=[0, 0, -1],
        #     rotation=[0, 0, 0, 1],
        # )],
        meshes=[
            pygltflib.Mesh(
                primitives=[
                    pygltflib.Primitive(
                        attributes=pygltflib.Attributes(POSITION=0, TEXCOORD_0=1),
                        mode=pygltflib.TRIANGLES,
                        material=0
                    )
                ]
            )
        ],
        buffers=[
            pygltflib.Buffer(
                byteLength=len(xyz_binary_blob) 
                + len(uv_binary_blob) 
                #+ len(animation_binary_blob)
            )
        ],
        bufferViews=[
            # XYZ
            pygltflib.BufferView(
                buffer=0,
                byteOffset=0,
                byteLength=len(xyz_binary_blob),
                target=pygltflib.ARRAY_BUFFER,
            ),
            # UV
            pygltflib.BufferView(
                buffer=0,
                byteOffset=len(xyz_binary_blob),
                byteLength=len(uv_binary_blob),
                target=pygltflib.ARRAY_BUFFER,
            ),
            # Animation Times
            # pygltflib.BufferView(
            #     buffer=0,
            #     byteOffset=len(xyz_binary_blob)
            #         + len(uv_binary_blob),
            #     byteLength=20,
            # ),
            # # Animation Values
            # pygltflib.BufferView(
            #     buffer=0,
            #     byteOffset=len(xyz_binary_blob)
            #         + len(uv_binary_blob)
            #         + 20,
            #     byteLength=80,
            # ),
        ],
        accessors=[
            pygltflib.Accessor(
                bufferView=0,
                componentType=pygltflib.FLOAT,
                count=len(xyz),
                type=pygltflib.VEC3,
                max=xyz.max(axis=0).tolist(),
                min=xyz.min(axis=0).tolist(),
            ),
            pygltflib.Accessor(
                bufferView=1,
                componentType=pygltflib.FLOAT,
                count=len(uv),
                type=pygltflib.VEC2,
                max=uv.max(axis=0).tolist(),
                min=uv.min(axis=0).tolist(),
            ),
            # pygltflib.Accessor(
            #     bufferView=2,
            #     componentType=pygltflib.FLOAT,
            #     count=5,
            #     type=pygltflib.SCALAR,
            #     max=[4.0],
            #     min=[0.0],
            # ),
            # pygltflib.Accessor(
            #     bufferView=3,
            #     componentType=pygltflib.FLOAT,
            #     count=5,
            #     type=pygltflib.VEC4,
            #     max=[0.0, 0.0, 1.0, 1.0],
            #     min=[0.0, 0.0, 0.0, -0.707],
            # )
        ],
        images=[
            pygltflib.Image(
                uri=img,
                mimeType="image/jpeg",
            )
        ],
        # samplers=[
        #     pygltflib.Sampler(
        #         magFilter=pygltflib.LINEAR,
        #         minFilter=pygltflib.LINEAR,
        #         wrapS=pygltflib.CLAMP_TO_EDGE,
        #         wrapT=pygltflib.CLAMP_TO_EDGE
        #     ),
        # ],
        textures=[
            pygltflib.Texture(
                #sampler=0,
                source=0
            )
        ],
        materials=[
            pygltflib.Material(
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                    baseColorTexture=pygltflib.TextureInfo(
                        index=0,
                    ),
                    metallicFactor=0.0,
                ),
                doubleSided=True,
            )
        ],
        # animations=[
        #     pygltflib.Animation(
        #         channels=[
        #             pygltflib.AnimationChannel(
        #                 sampler=0,
        #                 target=pygltflib.AnimationChannelTarget(
        #                     node=0,
        #                     path="rotation"
        #                 ),
        #             )
        #         ],
        #         samplers=[
        #             pygltflib.AnimationSampler(
        #                 input=2,
        #                 interpolation="LINEAR",
        #                 output=3
        #             )
        #         ]
        #     )
        # ],
        # cameras=[
        #     pygltflib.Camera(
        #         type="perspective",
        #         perspective=pygltflib.Perspective(
        #             yfov=np.pi / 2,
        #             aspectRatio=1.0,
        #             znear=0.01,
        #             zfar=100.0
        #         )
        #     )
        # ]
    )
    gltf.set_binary_blob(xyz_binary_blob + uv_binary_blob)# + animation_binary_blob)
    #gltf.convert_buffers(pygltflib.BufferFormat.BINFILE)
    gltf.save(f"gltf/fragment-{number}.glb")

def main():
    gltf = pygltflib.GLTF2().load('source/8k.glb')
    os.makedirs("gltf", exist_ok=True)
    os.makedirs("png", exist_ok=True)
    node = gltf.nodes[0]
    mesh = gltf.meshes[node.mesh]
    indicesAccessor = gltf.accessors[mesh.primitives[0].indices]
    indices = get_indices(gltf, indicesAccessor)
    xyzAccessor = gltf.accessors[mesh.primitives[0].attributes.POSITION]
    xyz = get_xyz(gltf, xyzAccessor)
    uvAccessor = gltf.accessors[mesh.primitives[0].attributes.TEXCOORD_0]
    uv = get_uv(gltf, uvAccessor)
    image = get_image(gltf, gltf.materials[0].pbrMetallicRoughness.baseColorTexture.index)
    number = 1
    start = (TRICOUNT * 3) * 2
    #while number < len(Q.keys()):
    while start < len(indices):
        print(f"{number} ", end = "", flush=True)
        if len(indices) - start < TRICOUNT * 3:
            numvertices = len(indices) - start
        else:
            numvertices = TRICOUNT * 3
        save_fragment(indices, xyz, uv, image, number, start, numvertices)
        start = start + numvertices
        number = number + 1
    print()

if __name__ == "__main__":
    main()
