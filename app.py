from typing import Dict
from bs4 import BeautifulSoup, ResultSet, Tag
import re
import zipfile
import os


def create_answerkey_dict(soup: BeautifulSoup) -> Dict[str, str]:
    answers: ResultSet[Tag] = soup.find_all("p", class_=re.compile(r'ans_key\d+'))

    if len(answers) == 0:
        print("Couldn't find answer key")
        exit()

    answer_dict: Dict[str, str] = {}

    for answer in answers:
        number = answer.find('a').get_text()
        answer_str = answer.find('span').get_text()
        letter_answer_list = re.findall(r'[A-Z]', answer_str)

        answer_dict[number] = letter_answer_list

    return answer_dict

def get_chapter_heading(soup: BeautifulSoup) -> str:
    output = '## '

    headings = soup.find_all("h2")

    for h2 in headings:
        output += f'{h2.get_text()} '

    return output.strip() + '\n\n'

def get_question_with_choices(soup: BeautifulSoup, answer_key_dict: Dict[str, str]) -> str:
    output = ''
    paragraphs: ResultSet[Tag] = soup.find_all('p', {'class', 'quiz'})

    for p in paragraphs:
        output += f'{p.get_text()}\n\n'

        question_num = p.find('a').get_text()

        ol = p.find_next_sibling('ol', {'class', 'lower-alpha'})
        if ol is None:
            raise RuntimeError("\tCoulding find ordered list of answers")

        choice_list_items = ol.find_all("li")

        for i, li in enumerate(choice_list_items):
            # choices are uppercase lettered
            curr_choice_letter = chr(i + ord('A'))

            if curr_choice_letter in answer_key_dict[question_num]:
                output += f'- [x] {curr_choice_letter}. {li.get_text()}\n'
            else:
                output += f'- [ ] {curr_choice_letter}. {li.get_text()}\n'

        output += '\n'

    return output

def extract_necessary_files(epub_file_path: str, extraction_dir: str):
    filename_pattern = re.compile(r'OEBPS/xhtml/vol(1|2)_ch\d\d\.xhtml')

    with zipfile.ZipFile(epub_file_path, 'r') as zip_ref:
        epub_filename_list = zip_ref.namelist()

        for needed_filename in epub_filename_list:
            if filename_pattern.match(needed_filename):
                zip_ref.extract(needed_filename, extraction_dir)

def chapter_has_no_quiz(chapter_filename: str) -> bool:
    has_no_quiz = False

    no_quiz_chapters = ['vol1_ch20', 'vol1_ch30', 'vol2_ch25', 'vol2_ch26']

    for chapter in no_quiz_chapters:
        if chapter in chapter_filename:
            has_no_quiz = True

    return has_no_quiz


def main():

    epub_file_path = 'book.epub'
    extraction_dir = 'extraction'

    extract_necessary_files(epub_file_path, extraction_dir)

    xhtml_dir_path = os.path.join(extraction_dir, 'OEBPS/xhtml/')
    xhtml_filename_list = sorted(os.listdir(xhtml_dir_path))


    with open('test.md', 'w') as output_file:
        for xhtml_file in xhtml_filename_list:
            output = ''
            xhtml_file_path = os.path.join(xhtml_dir_path, xhtml_file)

            # skip chapters that dont have a quiz
            if chapter_has_no_quiz(xhtml_file):
                continue

            with open(xhtml_file_path, 'r', encoding='utf-8') as file:
                soup = BeautifulSoup(file, "lxml-xml")  # Use lxml parser for XHTML

                chapter_heading_text = get_chapter_heading(soup)
                output += chapter_heading_text

                answer_key_dict = create_answerkey_dict(soup);

                question_text = get_question_with_choices(soup, answer_key_dict);
                output += question_text

                output_file.write(output)


if __name__ == "__main__":
    main()





