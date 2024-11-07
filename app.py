from typing import Dict
from bs4 import BeautifulSoup, ResultSet, Tag
import pprint
import lxml
import re


def create_answerkey_dict(soup: BeautifulSoup) -> Dict[str, str]:
    answers: ResultSet[Tag] = soup.find_all("p", class_=re.compile(r'ans_key\d'))

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
                output += f'- [x] {li.get_text()}\n'
            else:
                output += f'- [ ] {li.get_text()}\n'

        output += '\n'

    return output




def main():
    output = ''

    with open("./extraction/OEBPS/xhtml/vol1_ch01.xhtml", "r") as file:
        soup = BeautifulSoup(file, "lxml-xml")  # Use lxml parser for XHTML


    chapter_heading_text = get_chapter_heading(soup)
    output += chapter_heading_text

    answer_key_dict = create_answerkey_dict(soup);

    question_text = get_question_with_choices(soup, answer_key_dict);
    output += question_text

    print(output)





if __name__ == "__main__":
    main()





