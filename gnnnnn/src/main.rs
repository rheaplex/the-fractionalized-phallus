use std::boxed::Box;
use std::error::Error as StdError;
use gltf;

// We acctually copy rectangles....
fn copy_pixels_for_triangles(pixels: &gltf::image::Data, uv: &[[f32;2]], triangles: &[[f32;3]]) -> Vec<u8> {
    let mut dest: Vec<u8> = Vec::with_capacity(pixels.pixels.len());

    for triangle in triangles {
        let p0 = uv[triangle[0] as usize];
        let p1 = uv[triangle[1] as usize];
        let p2 = uv[triangle[2] as usize];
        let left = (p0[0].min(p1[0]).min(p2[0]) * pixels.width as f32) as usize;
        let right = (p0[0].max(p1[0]).max(p2[0]) * pixels.width as f32) as usize;
        let top = (p0[1].max(p1[1]).max(p2[1]) * pixels.height as f32) as usize;
        let bottom = (p0[1].min(p1[1]).min(p2[1]) * pixels.height as f32) as usize;
        for x in left..right {
            for y in bottom..top {
                let index: usize = ((y * pixels.width as usize) + x) * 3;
                dest[index] = pixels.pixels[index];
                dest[index + 1] = pixels.pixels[index + 1];
                dest[index + 2] = pixels.pixels[index + 2];
            }
        }
    }
    dest
}

fn main() -> Result<(), Box<dyn StdError>> {
    let stride = 3;
    let (source, buffers, images) = gltf::import("src/1k.gltf")?;
    let mesh = source.meshes().next().expect("no mesh");
    let primitive = mesh.primitives().next().expect("no mesh");
    let reader = primitive.reader(|buffer| Some(&buffers[buffer.index()]));
    let xyz: Vec<[f32;3]> = reader.read_positions().expect("no positions").collect();
    let uv: Vec<[f32;2]> = reader.read_tex_coords(0).expect("no texture coords").into_f32().collect();
    let mut indices: Vec<u32> = reader.read_indices().expect("no point indices").into_u32().collect();
    
    let img = &images[0];

    assert!(img.format == gltf::image::Format::R8G8B8);
    assert!(img.pixels.len() == (img.width * img.height * 3) as usize);

    while indices.len() >= stride * 3 {
        let which = indices.drain(0..stride * 3).collect::<Vec<u32>>();
        let triangles = which.iter().map(|&i| xyz[i as usize]).collect::<Vec<[f32;3]>>();
        let tex_coords = which.iter().map(|&i| uv[i as usize]).collect::<Vec<[f32;2]>>();
        let new_img = copy_pixels_for_triangles(img, &tex_coords, &triangles);
    }
    
    println!("{xyz:?}\n{uv:?}\n{indices:?}\n{img:?}");

    Ok(())
}
