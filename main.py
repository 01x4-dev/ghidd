import json
import networkx as nx
import openai
from openai import OpenAI
import os
import re
import requests
import sys
from types import SimpleNamespace

BASE_API_URL = "https://api.github.com/repos/" + os.environ['OWNER_REPO']
REST_API_HEADER = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ['PAT']}",
    "X-GitHub-Api-Version": "2022-11-28"
}

issues_objs = []
udg = nx.Graph()
usg = []

def trim_text(text):
    """Trims text length to arbitrary value for mitigating API tokens consumption and related speed/cost
    while still returning accurate response from good-enough context understanding

    :param text: text to trim if too long, if not does nothing
    :type text: str
    :returns: trimmed text (empty if input was null)
    :rtype: str
    """
    MAX_TEXT_LENGTH = 500
    return text[:MAX_TEXT_LENGTH] if text is not None else str()

def post_rest_api(endpoint_url, payload):
    """POST method of an HTTP request

    :param endpoint_url: URL of the target endpoint
    :type endpoint_url: str
    :param payload: object to write, automatically converted to JSON
    :type payload: dict
    """
    response = requests.post(endpoint_url, headers=REST_API_HEADER, data=json.dumps(payload))

def get_rest_api(endpoint_url):
    """GET method of an HTTP request

    :param endpoint_url: URL of the target endpoint
    :type endpoint_url: str
    :returns: JSON-encoded response of the REST API call
    :rtype: Any | None
    """
    response = requests.get(endpoint_url, headers=REST_API_HEADER)
    return response.json() if response.ok else None

def exists_duplicate_label():
    """Check repo has duplicate label available and creates it if not """
    json_response = get_rest_api(BASE_API_URL + "/labels")
    labels_cnt = len(json_response)
    for label_idx in range(0, labels_cnt, 1):
        label_obj = SimpleNamespace(**json_response[label_idx])
        dupl_label = json.loads(os.environ["INPUT_DUPLLABEL"])
        if dupl_label["name"] in label_obj.name: return
    post_rest_api(BASE_API_URL + "/labels", dupl_label)

def get_all_repo_issues() -> bool:
    """Get all repo open issues and validates the set

    :returns: Whether or not the returned set is valid for comparison operations (not null and more than one)
    :rtype: boolean
    """
    issues_objs.clear()
    json_response = get_rest_api(BASE_API_URL + "/issues")
    issues_cnt = len(json_response)
    for issue_idx in range(0, issues_cnt, 1):
        issues_objs.append(SimpleNamespace(**json_response[issue_idx]))
    return True if json_response is not None and len(issues_objs) > 1 else False

def has_duplicate_label(issue_num) -> bool:
    """Determines if this issue is tagged with duplicate label

    :param issue_num: Index of this GitHub issue indicated with #
    :type issue_num: int
    :returns: Whether or not this issue is already tagged with duplicate label
    :rtype: boolean
    """
    json_response = get_rest_api(BASE_API_URL + "/issues/" + str(issue_num) + "/labels")
    labels_cnt = len(json_response)
    for label_idx in range(0, labels_cnt, 1):
        label_obj = SimpleNamespace(**json_response[label_idx])
        dupl_label = json.loads(os.environ["INPUT_DUPLLABEL"])
        if dupl_label["name"] in label_obj.name: return True
    return False

def has_duplicate_comment(issue_num) -> bool :
    """Determines if this issue includes duplicate bot comment

    :param issue_num: Index of this GitHub issue indicated with #
    :type issue_num: int
    :returns: Whether or not this issue already has a bot comment describing this issue duplicates with another
    :rtype: boolean
    """
    json_response = get_rest_api(BASE_API_URL + "/issues/" + str(issue_num) + "/comments")
    comments_cnt = len(json_response)
    for comment_idx in range(0, comments_cnt, 1):
        comment_obj = SimpleNamespace(**json_response[comment_idx])
        if os.environ["INPUT_DUPLCMTH"] in comment_obj.body: return True
    return False

def set_github_action_output(name, value):
    """Set value to GITHUB_OUTPUT variable

    :param name: Variable name
    :type name: str
    :param value: Variable value to set
    :type value: str
    """
    with open(os.path.abspath(os.environ["GITHUB_OUTPUT"]), "a") as file_handle:
        print(f"{name}={value}", file=file_handle)

def traverse_udg(graph):
    """Traverse undirected dependency graph created

    :param graph: undirected dependency graph to traverse
    :type graph: Graph
    """
    if len(graph) > 0:
        nx.write_network_text(graph)
        for node in graph:
            sp = nx.shortest_path(graph, node)
            similar_issues = list(sp.keys())
            similar_issues.remove(node) # exclude itself
            print(f"#{node} itself excluded from similar issues {similar_issues}")
            issue_comment_body = os.environ["INPUT_DUPLCMTH"]
            for duplicate_issue_num in similar_issues:
                try:
                    probability = nx.get_edge_attributes(graph, "prob")[node, duplicate_issue_num]
                except KeyError as e:
                    probability = nx.get_edge_attributes(graph, "prob")[duplicate_issue_num, node]
                issue_comment_body += f"\nThis is duplicate of #{duplicate_issue_num} with {probability} confidence.\n"
            post_rest_api(BASE_API_URL + "/issues/" + str(node) + "/comments", { "body": issue_comment_body }) # write constructed duplicate comment to issue
            post_rest_api(BASE_API_URL + "/issues/" + str(node) + "/labels", { "labels": ["duplicate"] }) # tag issue with duplicate label
            print("Duplicate comment and label applied to #" + str(node))
    else:
        print("No new duplicates found in graph.")
    set_github_action_output('duplicates-found', len(graph))

def traverse_usg(l):
    """Traverse undirected star graph created

    :param l: custom-made implementation of unbalanced USG to traverse
    :type l: list of dict
    """
    if len(l) > 0:
        issue_comment_body = os.environ["INPUT_DUPLCMTH"]
        for elem in l:
            issue_comment_body += f'\nThis is duplicate of #{elem["end_node"]} with {elem["prob"]} confidence.\n'
        post_rest_api(BASE_API_URL + "/issues/" + str(elem["center_node"]) + "/comments", { "body": issue_comment_body }) # write constructed duplicate comment to issue
        post_rest_api(BASE_API_URL + "/issues/" + str(elem["center_node"]) + "/labels", { "labels": ["duplicate"] }) # tag issue with duplicate label
        print("Duplicate comment and label applied to #" + str(elem["center_node"]))
    else:
        print("No new duplicates found in graph.")
    set_github_action_output('duplicates-found', len(l))


def infer_cc(iA, iB) -> str:
    """Infer chat completion OpenAI model and return response

    :param iA: index of issue A to compare
    :type iA: int
    :param iB: index of issue B to compare
    :type iB: int
    :returns: AI model response
    :rtype: str
    """
    try:
        client = OpenAI()
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior software developer."},
                {"role": "user", "content": "Detect if these 2 software issues are about the same topic so they can be labeled as duplicate."},
                {"role": "user", "content": "Simply reply False if they are not, and True (x) if they are, where x is the confidence percentage value."},
                {"role": "user", "content": "Topic A: " + trim_text(issues_objs[iA].title) + ". " + trim_text(issues_objs[iA].body)},
                {"role": "user", "content": "Topic B: " + trim_text(issues_objs[iB].title) + ". " + trim_text(issues_objs[iB].body)}
            ]
        )
        return completion.choices[0].message.content
    except (
        openai.AuthenticationError,
        openai.PermissionDeniedError,
        openai.RateLimitError,
        openai.OpenAIError) as e:
        print(f"OpenAI API Error: {e}")
        raise SystemExit(1) # will result workflow to ${{ failure() }}

def main():
    exists_duplicate_label()
    if get_all_repo_issues():
        mode = sys.argv[1]
        match mode:
            case 'all':
                # loop through all open issues set found and cross check them all
                udg.clear()
                for issueA_idx in range(0, len(issues_objs) - 1, 1):
                    if not has_duplicate_label(issues_objs[issueA_idx].number) or not has_duplicate_comment(issues_objs[issueA_idx].number):
                        for issueB_idx in range(0, len(issues_objs), 1):
                            if issueA_idx < issueB_idx:
                                # only consider issue pairs within the feasible region of the overall constraint matrix
                                is_duplicate = infer_cc(issueA_idx, issueB_idx)
                                if "True" in is_duplicate:
                                    regex_match = re.findall(r'\d+(?:\.\d+)?', is_duplicate)
                                    udg.add_edge(issues_objs[issueA_idx].number, issues_objs[issueB_idx].number, conf = float(regex_match[0]) / 100.0, prob = str(regex_match[0]) + "%")
                                print(f'Issue #{issues_objs[issueA_idx].number} compared with #{issues_objs[issueB_idx].number} : {is_duplicate}')
                    else:
                        print("Issue #" + str(issues_objs[issueA_idx].number) + " already detected as duplicate, skip it.")
                traverse_udg(udg)
            case 'new':
                usg.clear()
                # only compare new issue with the rest of the list
                for issueB_idx in range(1, len(issues_objs), 1):
                    is_duplicate = infer_cc(0, issueB_idx)
                    if "True" in is_duplicate:
                        regex_match = re.findall(r'\d+(?:\.\d+)?', is_duplicate)
                        usg.append({"center_node" : issues_objs[0].number, "end_node" : issues_objs[issueB_idx].number, "conf" : float(regex_match[0]) / 100.0, "prob" : str(regex_match[0]) + "%"})
                    print(f'Issue #{issues_objs[0].number} compared with #{issues_objs[issueB_idx].number} : {is_duplicate}')
                traverse_usg(usg)
            case _:
                print(f"Unsupported mode {mode}, abort")
                raise SystemExit(1) # will result workflow to ${{ failure() }}
    else:
        print("Zero" if len(issues_objs) == 0 else "Less than 2" + " issues retrieved, cannot compare.")

if __name__ == "__main__":
    main()
