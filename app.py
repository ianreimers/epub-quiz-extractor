from typing import Dict
from bs4 import BeautifulSoup, ResultSet, Tag
import re
import zipfile
import os
import argparse
import sys
from pprint import pprint
from contextlib import ExitStack


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
        output += f"{p.get_text()}\n\n"

        a_tag = p.a
        if not a_tag:
            raise RuntimeError(
                f"Unable to find anchor tag inside the question paragraph: {output}"
            )

        href_attr = a_tag["href"]
        if isinstance(href_attr, list):
            raise RuntimeError("Multiple hrefs found in anchor tag")

        volume_p_id = href_attr.split("#")[1][:-1]
        question_num = a_tag.get_text()

        ol = p.find_next_sibling("ol", {"class", "lower-alpha"})
        if ol is None:
            raise RuntimeError("\tCouldn't find ordered list of answers")

        choice_list_items = ol.find_all("li")

        for i, li in enumerate(choice_list_items):
            # choices are uppercase lettered
            curr_choice_letter = chr(i + ord("A"))

            if curr_choice_letter in answer_key_dict[question_num]:
                output += f"- [x] {curr_choice_letter}. {li.get_text()}\n"
            else:
                output += f"- [ ] {curr_choice_letter}. {li.get_text()}\n"

        p_explanation = explanation_soup.find("a", id=volume_p_id).find_parent(
            "p", class_="quiz"
        )
        output += f"\n**Explanation**: {p_explanation}\n"

        output += "\n"

    return output


def extract_necessary_files(epub_file_path: str, extraction_dir: str):
    filename_pattern = re.compile(r"OEBPS/xhtml/vol(1|2)_ch\d\d\.xhtml")

    with zipfile.ZipFile(epub_file_path, "r") as zip_ref:
        epub_filename_list = zip_ref.namelist()

        for filename in epub_filename_list:
            if filename_pattern.match(filename) or "appc" in filename:
                zip_ref.extract(filename, extraction_dir)


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

    xhtml_dir_path = os.path.join(extraction_dir, "OEBPS/xhtml/")
    xhtml_filename_list = sorted(os.listdir(xhtml_dir_path))
    vol1_filename = "vol1_appc.xhtml"
    vol2_filename = "vol2_appc.xhtml"
    vol1_explanations_path = os.path.join(xhtml_dir_path, vol1_filename)
    vol2_explanations_path = os.path.join(xhtml_dir_path, vol2_filename)

    if vol1_filename not in xhtml_filename_list:
        raise RuntimeError(
            f"Volume 1 explantation file not found in extracted directory: {vol1_explanations_path}"
        )

    if vol2_filename not in xhtml_filename_list:
        raise RuntimeError(
            "Volume 2 explantation file not found in extracted directory"
        )

    with ExitStack() as stack:
        output_file = stack.enter_context(open("test.md", "w"))
        vol1_file = stack.enter_context(open(vol1_explanations_path))
        vol2_file = stack.enter_context(open(vol2_explanations_path))

        switched = False
        explanation_soup = BeautifulSoup(vol1_file, "lxml-xml")

        for xhtml_filename in xhtml_filename_list:
            output = ""
            xhtml_file_path = os.path.join(xhtml_dir_path, xhtml_filename)
            curr_volume = get_curr_volume(xhtml_filename)
            if curr_volume == 2 and not switched:
                explanation_soup = BeautifulSoup(vol2_file, "lxml-xml")
                switched = True

            # print(explanation_soup)

            # skip chapters that dont have a quiz
            if chapter_has_no_quiz(xhtml_filename):
                continue

            if "appc" in xhtml_filename:
                continue

            with open(xhtml_file_path, "r", encoding="utf-8") as file:
                # Use lxml parser for XHTML
                soup = BeautifulSoup(file, "lxml-xml")
                # print(curr_volume)

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
