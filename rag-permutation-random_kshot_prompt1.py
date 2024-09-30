from llama_cpp import Llama
from compose_prompts import *
from llama_tools import llama_tools
from experiment_tools import *
from prompt1_tools import *
import json
import sys
from permutation_generator import *

# def llama_call(llm, prompt, temperature):
      
#       output = llm(
#                   prompt, # Prompt
#                   max_tokens=300, # Generate up to 300 tokens, set to None to generate up to the end of the context window
#                   stop=["STOP"], # Stop generating just before the model would generate a new question
#                   echo=False, # Echo the prompt back in the output
#                   logprobs=50,
#                   top_k=50,
#                   temperature=temperature,
#             ) # Generate a completion, can also call create_completion
      
#       return output
    
# def compose_context_with_permutations(res, qid: str, batch_size, batch_step, top_starts, tail_starts, doc_dict):
#       print(qid)
#       retrieved_for_q = res[res.qid==qid]
#       retrieved_num = retrieved_for_q['rank'].max()+1
      
#       starts = list(range(0, (retrieved_num-1)-(batch_size-1)+1, batch_step))
#       start_rank_list = list(set(starts[:top_starts]).union(set(starts[(len(starts)-1)-(tail_starts-1):])))
#       print(start_rank_list)
#       start_rank_list.sort()
      
#       p_name_list = []
#       context_book = []
#       for start in start_rank_list:
#             end = start + batch_size
#             batch_docnos = retrieved_for_q[(retrieved_for_q['rank']>=start)&(retrieved_for_q['rank']<end)].docno.tolist()

#             permuntation_docnos = get_permutation(batch_docnos, len(batch_docnos))
            
#             for p_name, p_batch_docnos in permuntation_docnos.items():
#                   context = ''
                  
#                   batch_texts = [doc_dict[str(docno)] for docno in p_batch_docnos]
#                   num = 0
#                   for text in batch_texts:
#                         num += 1
#                         context += f'Context {num}: {text};\n'
                  
#                   p_name_list.append(f'{start}>{p_name}')
#                   context_book.append(context)
            
#       return p_name_list, context_book
            
# def load_llama():
      
#       import torch
#       print(torch.__version__)
#       device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
#       print(device)
      
#       llm = Llama(
#             model_path="../Meta-Llama-3-8B-Instruct/Meta-Llama-3-8B-Instruct.Q8_0.gguf",
#             logits_all=True,
#             verbose=False,
#             n_gpu_layers=-1, # Uncomment to use GPU acceleration
#             n_ctx=2048, # Uncomment to increase the context window
#       )

#       llm.set_seed(1000)
#       return llm

# def update_json_result_file(file_name, result_to_write):
#       f = open(file_name, "w+", encoding='UTF-8')
#       json.dump(result_to_write, f, indent=4)
#       f.close()

# # prepare needed files
# def prepare_data():
#       # read the retrieved documents
#       import pickle
#       with open('./middle_products/msmarco_passage_v1_retrieved_top_tail.pkl', 'rb') as f:
#             doc_dict = pickle.load(f)
#             f.close()
#       # prepare queries
#       queries = pd.read_csv('./middle_products/queries_19.csv')
#       # prepare res file
#       res = pd.read_csv('./res/bm25_dl_19.csv') # retrieval result
      
#       return doc_dict, queries, res

# def single_call(llm, prompt, temperature):
#       output = llama_call(llm, prompt, temperature)
                  
#       # logprob_dict = output['choices'][0]['logprobs']['top_logprobs']
#       token_logprobs = output['choices'][0]['logprobs']['token_logprobs']
#       prob_seq = sum(token_logprobs)
                  
#       answer = output['choices'][0]['text']
                  
#       result = {"answer": answer, "prob_seq": float(prob_seq)}
#       return result

if __name__=="__main__":
      if(len(sys.argv) != 9):
            print("This experiment takes 8 parameters: ")
            print("1.batch size\n2.batch step\n3.num of calls\n4.top of starts\n5.tail of starts\ntemperature\nwhether_exam_full_permutations\n19/20")
            print("e.g. 1 1 1 10 0 0.2 False")

      batch_size = int(sys.argv[1])
      batch_step = int(sys.argv[2])
      num_calls = int(sys.argv[3])
      # start control parameters
      top_starts = int(sys.argv[4])
      tail_starts = int(sys.argv[5])
      temperature = float(sys.argv[6])
      full_permutation = eval(sys.argv[7])
      print('input', full_permutation)
      dataset_name = str(sys.argv[8])
      
      # load the llm
      llm = llama_tools.load_llama()
      # load needed data
      doc_dict, queries, res = prepare_data(dataset_name)
      
      setting_file_name = f'./middle_products/random_answers_{batch_size}shot_{num_calls}calls_{top_starts}_{tail_starts}_dl_{dataset_name}_settings_p_prompt1.json'
      setting_record = {'batch_size':batch_size, 'batch_step':batch_step, 'num_calls':num_calls, \
                  'top_starts':top_starts, 'tail_starts':tail_starts, 'temperature':temperature}
      f = open(setting_file_name, "w+", encoding='UTF-8')
      json.dump(setting_record, f, indent=4)
      f.close()

      file_name = f'./middle_products/random_answers_{batch_size}shot_{num_calls}calls_{top_starts}_{tail_starts}_dl_{dataset_name}_p_prompt1.json'
      # result_to_write = {} #{qid:result_for_qid}

      try:
            f = open(file=file_name, mode="r")
            result_to_write = json.load(f)
            existed_qids = len(result_to_write)
            existed_qids_list = list(result_to_write.keys())
            f.close()
      except:
            f = open(file=file_name, mode="w+")
            result_to_write= {}
            existed_qids = 0
            existed_qids_list = []
            f.close()

      preamble = "Please answer this question based on the given context. End your answer with STOP."

      q_no = 0
      for qid, query in zip(queries['qid'].tolist(), queries['query'].tolist()):
            print(f'q_number={q_no}--{qid}')
            if(str(qid) in existed_qids_list):
                  print("Already generated, next!")
                  continue
            q_no += 1
            varying_context_result = {} #{start: results}
            
            start_records, context_book = compose_context_with_permutations(qid=qid, res=res, batch_size=batch_size, batch_step=batch_step, \
                  top_starts=top_starts, tail_starts=tail_starts, doc_dict=doc_dict, full_permutations=full_permutation)
            print('start records: ', start_records)

            for start, context in zip(start_records, context_book):
                  print(f'\tstart_rank.{start}')
                  prompt = f'{preamble} \n{context}Question: "{query}"\nNow start your answer. \nAnswer: '
                  print(prompt)
                  multi_call_results = {}
                  varying_context_result.update({start: multi_call_results})
                  
                  for j in range(num_calls):
                        print(f'\t\tno.{j}')
                        result = llama_tools.single_call(llm=llm, prompt=prompt, temperature=temperature)
                        multi_call_results.update({j: result})
                        
            result_to_write.update({qid: varying_context_result})              
            update_json_result_file(file_name=file_name, result_to_write=result_to_write)
            
      del llm