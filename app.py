import functools
from runtime.common import device, guarded, image_rgb, model_path, output_path, page_header


@functools.lru_cache(maxsize=1)
def model_and_processor():
    from transformers import Sam2Model, Sam2Processor
    directory = model_path()
    return Sam2Model.from_pretrained(directory).to(device()).eval(), Sam2Processor.from_pretrained(directory)


@guarded
def segment(image, x, y):
    import numpy as np
    import torch
    from PIL import Image
    image = image_rgb(image)
    x, y = int(x), int(y)
    if not (0 <= x < image.width and 0 <= y < image.height):
        raise ValueError("请在图片上点击要分割的物体")
    model, processor = model_and_processor()
    inputs = processor(images=image, input_points=[[[[x, y]]]], input_labels=[[[1]]], return_tensors="pt").to(device())
    with torch.inference_mode():
        outputs = model(**inputs)
    masks = processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"].cpu())[0]
    # one image / one point batch / multiple candidate masks
    index = outputs.iou_scores[0, 0].argmax().item()
    mask = masks[0, index].numpy().astype(np.uint8)*255
    alpha = Image.fromarray(mask, mode="L")
    cutout = image.convert("RGBA")
    cutout.putalpha(alpha)
    mask_path, cutout_path = output_path(".png"), output_path(".png")
    alpha.save(mask_path)
    cutout.save(cutout_path)
    return cutout, str(cutout_path), str(mask_path)


def build_ui():
    import gradio as gr
    with gr.Blocks(title="SAM2.1 分割") as ui:
        page_header()
        source = gr.Image(type="pil", label="上传图片，然后点击目标物体")
        with gr.Row():
            x = gr.Number(value=0, precision=0, label="选中点 X")
            y = gr.Number(value=0, precision=0, label="选中点 Y")
        def select_point(event: gr.SelectData):
            return event.index[0], event.index[1]
        source.select(select_point, outputs=[x, y])
        button = gr.Button("分割选中物体", variant="primary")
        preview = gr.Image(type="pil", image_mode="RGBA", label="透明物体")
        cutout = gr.File(label="下载物体 PNG")
        mask = gr.File(label="下载黑白蒙版")
        button.click(segment, [source, x, y], [preview, cutout, mask], api_name="segment")
    return ui
