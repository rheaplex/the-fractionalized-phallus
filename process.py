
import numpy
from numpy.lib.stride_tricks import sliding_window_view
import pygltflib
from PIL import Image, ImageDraw, ImageFilter
import os
import base64
import struct
import io

TRICOUNT = 33

ANIMATION_TIMES = numpy.array(
    [0, 1.0, 2.0, 3.0, 4.0],
    dtype=numpy.float32
    )

ANIMATION_VALUES = numpy.array([
    [0.0, 0.0, 0.0, 1.0 ],
    [0.0, 0.707, 0.0, 0.707],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.707, 0.0, -0.707],
    [0.0, 0.0, 0.0, 1.0]
], dtype=numpy.float32)

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
            width=3)
    im.paste(image, mask=mask)
    mask.save("dest/fragment-1.png")
    jpeg = io.BytesIO()
    im.save(jpeg, format="jpeg", quality="high")
    b64 = base64.standard_b64encode(jpeg.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"

COMPONENT_TYPES = {
    5120: numpy.int8,
    5121: numpy.uint8,
    5122: numpy.int16,
    5123: numpy.uint16,
    5125: numpy.uint32,
    5126: numpy.float32,
}

def accessor_component_type(accessor):
    return numpy.dtype(COMPONENT_TYPES[accessor.componentType])

def get_data(gltf, accessor):
    bufferView = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferView.buffer]
    data = gltf.get_data_from_buffer_uri(buffer.uri)
    offset = bufferView.byteOffset + accessor.byteOffset or 0
    return data[offset:]

def get_indices(gltf, accessor):
    data = get_data(gltf, accessor)
    coords = numpy.frombuffer(
        data,
        dtype=accessor_component_type(accessor),
        count=accessor.count
        )
    return coords

def get_xyz(gltf, accessor):
    data = get_data(gltf, accessor)
    coords = numpy.frombuffer(
        data,
        dtype=accessor_component_type(accessor).newbyteorder('<'),
        count=accessor.count * 3
        )
    return sliding_window_view(coords, window_shape = 3)[::3]


def get_uv(gltf, accessor):
    data = get_data(gltf, accessor)
    coords = numpy.frombuffer(
        data,
        dtype=accessor_component_type(accessor).newbyteorder('<'),
        count=accessor.count * 2
        )
    return sliding_window_view(coords, window_shape = 2)[::2]

def get_image(gltf, index):
    img = gltf.images[index]
    b64 = img.uri[len("data:image/jpeg;base64,"):]
    data = base64.standard_b64decode(b64)
    return Image.open(io.BytesIO(data))

def save_fragment(sourceIndices, sourceXYZ, sourceUV, sourceImage, number, start, tricount):
    indices = sourceIndices[range(start, start + (tricount * 3))]
    xyz = sourceXYZ[indices]
    uv = sourceUV[indices]
    img = subset_image(sourceImage, uv)
    xyz_binary_blob = xyz.flatten().tobytes()
    uv_binary_blob = uv.flatten().tobytes()
    animation_binary_blob = numpy.array(ANIMATION_TIMES).flatten().tobytes() \
        + numpy.array(ANIMATION_VALUES).flatten().tobytes()
    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[0])],
        nodes=[pygltflib.Node(
            mesh=0,
            rotation=[0, 0, 0, 1],
            name="Y_UP"
        )],
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
                + len(animation_binary_blob)
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
            pygltflib.BufferView(
                buffer=0,
                byteOffset=len(xyz_binary_blob)
                    + len(uv_binary_blob),
                byteLength=20,
            ),
            # Animation Values
            pygltflib.BufferView(
                buffer=0,
                byteOffset=len(xyz_binary_blob)
                    + len(uv_binary_blob)
                    + 20,
                byteLength=80,
            ),
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
            pygltflib.Accessor(
                bufferView=2,
                componentType=pygltflib.FLOAT,
                count=5,
                type=pygltflib.SCALAR,
                max=[4.0],
                min=[0.0],
            ),
            pygltflib.Accessor(
                bufferView=3,
                componentType=pygltflib.FLOAT,
                count=5,
                type=pygltflib.VEC4,
                max=[0.0, 0.0, 1.0, 1.0],
                min=[0.0, 0.0, 0.0, -0.707],
            )
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
        animations=[
            pygltflib.Animation(
                channels=[
                    pygltflib.AnimationChannel(
                        sampler=0,
                        target=pygltflib.AnimationChannelTarget(
                            node=0,
                            path="rotation"
                        ),
                    )
                ],
                samplers=[
                    pygltflib.AnimationSampler(
                        input=2,
                        interpolation="LINEAR",
                        output=3
                    )
                ]
            )
        ]
    )
    gltf.set_binary_blob(xyz_binary_blob + uv_binary_blob + animation_binary_blob)
    #gltf.convert_buffers(pygltflib.BufferFormat.BINFILE)
    gltf.save(f"dest/fragment-{number}.gltf")

def main():
    gltf = pygltflib.GLTF2().load('source/1k.gltf')
    os.makedirs("dest", exist_ok=True)
    # 1 is the mesh
    node = gltf.nodes[1]
    mesh = gltf.meshes[node.mesh]
    indicesAccessor = gltf.accessors[mesh.primitives[0].indices]
    indices = get_indices(gltf, indicesAccessor)
    xyzAccessor = gltf.accessors[mesh.primitives[0].attributes.POSITION]
    xyz = get_xyz(gltf, xyzAccessor)
    uvAccessor = gltf.accessors[mesh.primitives[0].attributes.TEXCOORD_0]
    uv = get_uv(gltf, uvAccessor)
    image = get_image(gltf, gltf.materials[0].pbrMetallicRoughness.baseColorTexture.index)
    number = 1
    start = 0
    while start < len(xyz) // 3:
        save_fragment(indices, xyz, uv, image, number, start, TRICOUNT)
        start = start + TRICOUNT * 3
        number = number + 1

if __name__ == "__main__":
    main()
