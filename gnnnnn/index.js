import fs from 'fs';
import { Document, NodeIO, Primitive } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { center, weld } from '@gltf-transform/functions';

// Configure I/O.
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);

const source = await io.read('src/1k.gltf');
const sourceRoot = source.getRoot();
const sourceMesh = sourceRoot.listMeshes()[0];
const sourcePrim = sourceMesh.listPrimitives()[0];
const sourceXYZ = sourcePrim.getAttribute('POSITION');
const sourceUV = sourcePrim.getAttribute('TEXCOORD_0');
const sourceIndices = sourcePrim.getAttribute('TEXCOORD_0');

// Start is relative to number of triangles.
function createTextureCoords(uv, start, triCount) {
    // 6 = 3 points x 2 coordinates each
    return uv.getArray().slice(start * 6, (start * 6) + (triCount * 6));
}

// Start is relative to number of triangles.
// 9 = 3 points of 3 coordinates each
function createPositionCoords(xyz, start, triCount) {
    // 9 = 3 points x 3 coordinates each
    return xyz.getArray().slice(start * 9, (start * 9) + (triCount * 9));
}

// Start is relative to number of triangles.

function createTrianglesPrim(document, start, triCount) {
    const positionArray = createPositionCoords(sourceXYZ, start, triCount);;

    const buffer = document.getRoot().listBuffers()[0]
     || document.createBuffer();
    
     const position = document.createAccessor()
        .setType('VEC3')
        .setArray(positionArray)
        .setBuffer(buffer);
    
    // Indices in the vec3, so each is for one point.
    // * 3 = 3 points for each triangle.
    const indices = document
        .createAccessor()
        .setArray(new Uint16Array(triCount * 3).map((_, i) => i))
        .setBuffer(buffer);
    //console.log(indices.getArray())

    return document.createPrimitive()
        .setMode(Primitive.Mode.TRIANGLES)
        .setAttribute('POSITION', position)
        .setIndices(indices);
}

function createFragment(xyz, uv, start, triCount) {
    const document = new Document();

    const texture = document.createTexture('texture001')
        .setImage(fs.readFileSync('src/textures/0bd5599de27f82dfa7fcdba7b9ccf3a2.jpg'))
        .setMimeType('image/jpeg');

    const material = document.createMaterial('material001')
        //.setBaseColorFactor([1, 0.5, 0.5, 1]) // RGBA
        .setBaseColorTexture(texture);
    material.getBaseColorTextureInfo().setTexCoord(0);

    const texcoordArray = createTextureCoords(sourceUV, start, triCount);

    const primitive = createTrianglesPrim(document, start, triCount)
        .setAttribute('TEXCOORD_0', document.createAccessor('t').setType('VEC2').setArray(texcoordArray))
        .setMaterial(material);

    const mesh = document.createMesh('myMesh')
        .addPrimitive(primitive);

    const node = document.createNode()
        .setMesh(mesh)
        .setTranslation([0, 0, 0]);

    document.createScene().addChild(node);

    return document;
}

const frag = createFragment(sourceXYZ, sourceUV, 0, 8);
await io.write('test.gltf', frag);
    //.transform(scale({factor: 10.0}))
    //.transform(center({pivot: 'below'}))
    //    .transform(weld());


