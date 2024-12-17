from typing import Dict
from bs4 import BeautifulSoup, ResultSet, Tag
import re
import zipfile
import os
import argparse
import sys
from pprint import pprint
from contextlib import ExitStack
import shutil


def create_answerkey_dict(soup: BeautifulSoup) -> Dict[str, str]:
    answers: ResultSet[Tag] = soup.find_all("p", class_=re.compile(r"ans_key\d+"))

    if len(answers) == 0:
        raise RuntimeError(f"Couldn't find answer key")

    answer_dict: Dict[str, str] = {}

    for answer in answers:
        number = answer.find("a").get_text()
        answer_str = answer.find("span").get_text()
        letter_answer_list = re.findall(r"[A-Z]", answer_str)

        answer_dict[number] = letter_answer_list

    return answer_dict


def get_chapter_heading(soup: BeautifulSoup) -> str:
    output = "## "

    headings = soup.find_all("h2")

    for h2 in headings:
        output += f"{h2.get_text()} "

    return output.strip() + "\n\n"


def get_question_content(
    soup: BeautifulSoup,
    explanation_soup: BeautifulSoup,
    answer_key_dict: Dict[str, str],
) -> str:
    ## Question code snippets: (tag: <pre>, class: "pre-q")

    output = ""
    p_questions: ResultSet[Tag] = soup.find_all("p", {"class", "quiz"})

    for p in p_questions:
        question_text = p.get_text()
        output += f"{question_text}\n\n"

        a_tag = p.a
        if a_tag is None:
            raise ValueError(
                f"Unable to find anchor tag inside the question paragraph for question: {question_text}"
            )

        href_attr = a_tag["href"]
        if isinstance(href_attr, list):
            raise ValueError(
                f"Multiple hrefs found in anchor tag for question: {question_text}"
            )

        a_explanation_id = href_attr.split("#")[1][:-1]
        question_num = a_tag.get_text()

        ol = p.find_next_sibling("ol", {"class", "lower-alpha"})
        if ol is None or not isinstance(ol, Tag):
            raise ValueError(f"Ordered list not found for question: {question_text}")

        choice_list_items = ol.find_all("li")

        for i, li in enumerate(choice_list_items):
            # choices are uppercase lettered
            curr_choice_letter = chr(i + ord("A"))

            if curr_choice_letter in answer_key_dict[question_num]:
                output += f"- [x] {curr_choice_letter}. {li.get_text()}\n"
            else:
                output += f"- [ ] {curr_choice_letter}. {li.get_text()}\n"

        p_explanation = explanation_soup.find("a", id=a_explanation_id).find_parent(
            "p", class_="quiz"
        )
        p_explanation.a.extract()
        output += f"\n**Explanation**: {p_explanation}\n"

        output += "\n"

    return output


def extract_necessary_files(epub_file_path: str, extraction_dir: str):
    filename_pattern = re.compile(r"OEBPS/xhtml/vol(1|2)_ch\d\d\.xhtml")

    try:
        os.mkdir(extraction_dir)
    except FileExistsError:
        pass

    with zipfile.ZipFile(epub_file_path, "r") as zip_ref:
        file_paths = zip_ref.namelist()

        for file_path in file_paths:
            if filename_pattern.match(file_path) or "appc" in file_path:
                filename = os.path.basename(file_path)
                with open(os.path.join(extraction_dir, filename), "wb") as f:
                    f.write(zip_ref.read(file_path))


def chapter_has_no_quiz(chapter_filename: str) -> bool:
    has_no_quiz = False

    no_quiz_chapters = ["vol1_ch20", "vol1_ch30", "vol2_ch25", "vol2_ch26"]

    for chapter in no_quiz_chapters:
        if chapter in chapter_filename:
            has_no_quiz = True

    return has_no_quiz


def is_valid_ebook(path: str):
    return path.endswith(".epub")


def file_exists(path: str):
    return os.path.isfile(path)


def list_ebook_files(path: str):
    with zipfile.ZipFile(path, "r") as zip_ref:
        epub_filename_list = zip_ref.namelist()
        pprint(epub_filename_list)


def create_arg_parser():
    parser = argparse.ArgumentParser(
        prog="Ebook Quiz Extractor",
        description="Extracts question, choices, answers, and explanations from the ebook",
    )
    parser.add_argument(
        "-l",
        "--list",
        required=False,
        action="store_true",
        help="lists all files within the .epub file",
    )
    parser.add_argument(
        "input_file", type=str, help="the name of the .epub file to extract from"
    )
    parser.add_argument(
        "-o",
        "--output_file",
        type=str,
        default="quiz.md",
        required=False,
        help="name of the output markdown file",
    )
    return parser


def get_curr_volume(volume_filename: str):
    idx = volume_filename.find("vol")
    return int(volume_filename[idx + 3])


def main():
    parser = create_arg_parser()
    args = parser.parse_args()

    if not file_exists(args.input_file):
        print("File does not exist")
        raise FileNotFoundError(f"File '{args.input_file}' not found")

    if not is_valid_ebook(args.input_file):
        raise ValueError(f"Invalid epub file: {args.input_file} ")

    if args.list:
        list_ebook_files(args.input_file)
        return

    extraction_dir = "extraction"

    extract_necessary_files(args.input_file, extraction_dir)

    # xhtml_dir_path = os.path.join(extraction_dir, "OEBPS/xhtml/")
    filenames = sorted(os.listdir(extraction_dir))
    vol1_eplanations_filename = "vol1_appc.xhtml"
    vol2_explanation_filename = "vol2_appc.xhtml"
    vol1_explanations_filepath = os.path.join(extraction_dir, vol1_eplanations_filename)
    vol2_explanations_filepath = os.path.join(extraction_dir, vol2_explanation_filename)

    if vol1_eplanations_filename not in filenames:
        raise RuntimeError(
            f"Volume 1 explantation file not found in extracted directory: {vol1_explanations_filepath}"
        )

    if vol2_explanation_filename not in filenames:
        raise RuntimeError(
            "Volume 2 explantation file not found in extracted directory"
        )

    with ExitStack() as stack:
        output_file = stack.enter_context(open("test.md", "w"))
        vol1_file = stack.enter_context(open(vol1_explanations_filepath))
        vol2_file = stack.enter_context(open(vol2_explanations_filepath))

        is_vol2_soup = False
        explanation_soup = BeautifulSoup(vol1_file, "lxml-xml")

        for filename in filenames:
            output = ""
            file_path = os.path.join(extraction_dir, filename)
            curr_volume = get_curr_volume(filename)
            if curr_volume == 2 and not is_vol2_soup:
                explanation_soup = BeautifulSoup(vol2_file, "lxml-xml")
                is_vol2_soup = True

            # skip chapters that dont have a quiz
            if chapter_has_no_quiz(filename):
                continue

            if "appc" in filename:
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                # Use lxml parser for XHTML
                soup = BeautifulSoup(f, "lxml-xml")

                chapter_heading_text = get_chapter_heading(soup)
                output += chapter_heading_text

                answer_key_dict = create_answerkey_dict(soup)
                question_text = get_question_content(
                    soup, explanation_soup, answer_key_dict
                )
                output += question_text

                output_file.write(output)


if __name__ == "__main__":
    main()
