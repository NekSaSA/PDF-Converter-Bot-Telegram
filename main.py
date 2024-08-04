import asyncio
import logging
from io import BytesIO
from os import remove

from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from pdf2docx import Converter
from docx2pdf import convert
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image

API_TOKEN = '7290855598:AAHUz1msShLtBDZnOgEhSXd4jniAU2fTDOw'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

file_storage = {}
ACTIONS = ["Merge PDF", "Split PDF", "Convert to PDF", "Compress PDF", "PDF to Word", "Word to PDF"]

@dp.message(CommandStart())
async def send_welcome(message: Message):
    keyboard = InlineKeyboardBuilder()
    for action in ACTIONS:
        keyboard.add(InlineKeyboardButton(text=action, callback_data=action))
    keyboard.adjust(2)
    await message.answer("Hello! Select an action to work with PDF files:", reply_markup=keyboard.as_markup())

@dp.callback_query(F.data)
async def handle_action(callback_query: CallbackQuery):
    action = callback_query.data
    if action in ACTIONS:
        await bot.answer_callback_query(callback_query.id)
        await callback_query.message.answer(f"You have selected: {action}. Please upload the files.")
        file_storage[callback_query.from_user.id] = {'action': action, 'files': []}
    else:
        await callback_query.message.answer("Unknown action. Please try again.")

@dp.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id
    if user_id not in file_storage or 'action' not in file_storage[user_id]:
        await message.answer("Please select an action first.")
        return

    action = file_storage[user_id]['action']
    file_storage[user_id]['files'].append(message.document.file_id)
    await message.answer(
        f"File added. Current number of files: {len(file_storage[user_id]['files'])}. Send more or enter 'done'.")

@dp.message(F.text)
async def process_files(message: Message):
    user_id = message.from_user.id
    if message.text.lower() == "done" and user_id in file_storage and len(file_storage[user_id]['files']) > 0:
        await message.answer(f"Starting to process files for action: {file_storage[user_id]['action']}")
        action = file_storage[user_id]['action']

        if action == "Merge PDF":
            await merge_pdfs(user_id, message)
        elif action == "Split PDF":
            await split_pdf(user_id, message)
        elif action == "Convert IMG to PDF":
            await convert_to_pdf(user_id, message)
        elif action == "Compress PDF":
            await compress_pdf(user_id, message)
        elif action == "PDF to Word":
            await pdf_to_word(user_id, message)
        elif action == "Word to PDF":
            await word_to_pdf(user_id, message)

        del file_storage[user_id]
    else:
        await message.answer("Unknown command or no files added.")

async def merge_pdfs(user_id, message):
    merger = PdfMerger()
    for file_id in file_storage[user_id]['files']:
        file_info = await bot.get_file(file_id)
        file = await bot.download_file(file_info.file_path)
        merger.append(BytesIO(file.read()))

    output_path = f'{user_id}_merged.pdf'
    with open(output_path, 'wb') as f_out:
        merger.write(f_out)

    await send_file_to_user(user_id, message, output_path)

async def split_pdf(user_id, message):
    file_id = file_storage[user_id]['files'][0]
    file_info = await bot.get_file(file_id)
    file = await bot.download_file(file_info.file_path)

    reader = PdfReader(BytesIO(file.read()))
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        output_path = f'{user_id}_page_{i + 1}.pdf'
        with open(output_path, 'wb') as f_out:
            writer.write(f_out)
        await send_file_to_user(user_id, message, output_path)

async def convert_to_pdf(user_id, message):
    file_id = file_storage[user_id]['files'][0]
    file_info = await bot.get_file(file_id)
    file = await bot.download_file(file_info.file_path)
    file_ext = file_info.file_path.split('.')[-1].lower()

    if file_ext in ['jpg', 'jpeg', 'png', 'bmp', 'webp']:
        img = Image.open(BytesIO(file.read()))
        output_path = f'{user_id}_converted.pdf'
        img.save(output_path, "PDF", resolution=100.0)
        await send_file_to_user(user_id, message, output_path)
    else:
        await message.answer("This file type is not supported for PDF conversion.")

async def compress_pdf(user_id, message):
    file_id = file_storage[user_id]['files'][0]
    file_info = await bot.get_file(file_id)
    file = await bot.download_file(file_info.file_path)

    reader = PdfReader(BytesIO(file.read()))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    output_path = f'{user_id}_compressed.pdf'
    with open(output_path, 'wb') as f_out:
        writer.write(f_out)

    await send_file_to_user(user_id, message, output_path)

async def pdf_to_word(user_id, message):
    file_id = file_storage[user_id]['files'][0]
    file_info = await bot.get_file(file_id)
    file = await bot.download_file(file_info.file_path)

    output_path = f'{user_id}.docx'
    with open(output_path, 'wb') as f_out:
        cv = Converter(BytesIO(file.read()))
        cv.convert(f_out)
        cv.close()

    await send_file_to_user(user_id, message, output_path)

async def word_to_pdf(user_id, message):
    file_id = file_storage[user_id]['files'][0]
    file_info = await bot.get_file(file_id)
    file = await bot.download_file(file_info.file_path)

    output_path = f'{user_id}.pdf'
    with open(f'{user_id}.docx', 'wb') as f_out:
        f_out.write(file.read())

    convert(f'{user_id}.docx', output_path)
    remove(f'{user_id}.docx')

    await send_file_to_user(user_id, message, output_path)

async def send_file_to_user(user_id, message, file_path):
    input_file = FSInputFile(file_path)
    await bot.send_document(user_id, input_file)
    remove(file_path)
    await message.answer(f'File {file_path} sent successfully!')

async def on_shutdown(dp: Dispatcher):
    await bot.session.close()

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await on_shutdown(dp)

if __name__ == '__main__':
    asyncio.run(main())

