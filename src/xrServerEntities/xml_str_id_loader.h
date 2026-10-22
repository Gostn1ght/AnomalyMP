#pragma once

#ifdef XRGAME_EXPORTS
#	include "ui/xrUIXmlParser.h"
#else // XRGAME_EXPORTS
#	include "xrUIXmlParser.h"
#	include "object_broker.h"
#endif // XRGAME_EXPORTS


//T_ID    - уникальный текстовый идентификатор (аттрибут id в XML файле)
//T_INDEX - уникальный числовой индекс 
//T_INIT -  класс где определена статическая InitXmlIdToIndex
//          функция инициализации file_str и tag_name

//структура хранит строковый id элемента 
//файл и позицию, где этот элемент находится
struct ITEM_DATA
{
	shared_str id;
	int index;
	XML_NODE* node; // the item's element in _xml
	CUIXml* _xml;
};

typedef xr_vector<ITEM_DATA> T_VECTOR;

void _destroy_item_data_vector_cont(T_VECTOR* vec);

#define TEMPLATE_SPECIALIZATION template<typename T_INIT>
#define CSXML_IdToIndex CXML_IdToIndex<T_INIT>

TEMPLATE_SPECIALIZATION
class CXML_IdToIndex
{
public:

private:
	static T_VECTOR* m_pItemDataVector;
	// id -> position in m_pItemDataVector (ids are interned, hashing is by pointer)
	static xr_unordered_flat_map<shared_str, u32, std::hash<shared_str>>* m_pIdIndex;

protected:
	//имена xml файлов (разделенных запятой) из которых 
	//производить загрузку элементов
	static LPCSTR file_str;
	//имена тегов
	static LPCSTR tag_name;
public:
	CXML_IdToIndex();
	virtual ~CXML_IdToIndex();

	static void InitInternal();

	static const ITEM_DATA* GetById(const shared_str& str_id, bool no_assert = false);
	static const ITEM_DATA* GetByIndex(int index, bool no_assert = false);

	static const int IdToIndex(const shared_str& str_id, int default_index = T_INDEX(-1), bool no_assert = false)
	{
		const ITEM_DATA* item = GetById(str_id, no_assert);
		return item ? item->index : default_index;
	}

	static const shared_str IndexToId(int index, shared_str default_id = NULL, bool no_assert = false)
	{
		const ITEM_DATA* item = GetByIndex(index, no_assert);
		return item ? item->id : default_id;
	}

	static const int GetMaxIndex() { return m_pItemDataVector->size() - 1; }

	//удаление статичекого массива
	static void DeleteIdToIndexData();
};


TEMPLATE_SPECIALIZATION
typename T_VECTOR* CSXML_IdToIndex::m_pItemDataVector = NULL;
TEMPLATE_SPECIALIZATION
xr_unordered_flat_map<shared_str, u32, std::hash<shared_str>>* CSXML_IdToIndex::m_pIdIndex = NULL;

TEMPLATE_SPECIALIZATION
LPCSTR CSXML_IdToIndex::file_str = NULL;
TEMPLATE_SPECIALIZATION
LPCSTR CSXML_IdToIndex::tag_name = NULL;


TEMPLATE_SPECIALIZATION
CSXML_IdToIndex::CXML_IdToIndex()
{
}


TEMPLATE_SPECIALIZATION
CSXML_IdToIndex::~CXML_IdToIndex()
{
}


TEMPLATE_SPECIALIZATION
const typename ITEM_DATA* CSXML_IdToIndex::GetById(const shared_str& str_id, bool no_assert)
{
	T_INIT::InitXmlIdToIndex();
	const auto found = m_pIdIndex->find(str_id);
	if (found != m_pIdIndex->end())
		return &(*m_pItemDataVector)[found->second];

	Msg("item with id [%s] not found in files:", str_id.c_str());
	int i = 0;
	for (T_VECTOR::iterator it = m_pItemDataVector->begin(); m_pItemDataVector->end() != it; ++it, i++)
		Msg("[%d]=[%s]", i, *(*it).id);

	R_ASSERT3(no_assert, "item not found, id", str_id.c_str());
	return NULL;
}

TEMPLATE_SPECIALIZATION
const typename ITEM_DATA* CSXML_IdToIndex::GetByIndex(int index, bool no_assert)
{
	if ((size_t)index >= m_pItemDataVector->size())
	{
		R_ASSERT3(no_assert, "item by index not found in files", file_str);
		return NULL;
	}
	return &(*m_pItemDataVector)[index];
}

TEMPLATE_SPECIALIZATION
void CSXML_IdToIndex::DeleteIdToIndexData()
{
	VERIFY(m_pItemDataVector);
	_destroy_item_data_vector_cont(m_pItemDataVector);

	xr_delete(m_pItemDataVector);
	xr_delete(m_pIdIndex);
}

TEMPLATE_SPECIALIZATION
typename void CSXML_IdToIndex::InitInternal()
{
	VERIFY(!m_pItemDataVector);
	T_INIT::InitXmlIdToIndex();

	m_pItemDataVector = xr_new<T_VECTOR>();
	m_pIdIndex = xr_new<xr_unordered_flat_map<shared_str, u32, std::hash<shared_str>>>();

	VERIFY(file_str);
	VERIFY(tag_name);

	string_path xml_file;
	int count = _GetItemCount(file_str);
	int index = 0;
	for (int it = 0; it < count; ++it)
	{
		_GetItem(file_str, it, xml_file);

		CUIXml* uiXml = xr_new<CUIXml>();
		xr_string xml_file_full;
		xml_file_full = xml_file;
		xml_file_full += ".xml";
		uiXml->Load(CONFIG_PATH, "gameplay", xml_file_full.c_str());

		// Children with the tag in document order (as NavigateToNode(tag, i) counts them).
		XML_NODE* root = uiXml->GetRoot();
		int items_num = 0;
		for (XML_NODE* node = root ? root->FirstChild(tag_name) : nullptr; node; node = root->IterateChildren(tag_name, node), ++items_num)
		{
			LPCSTR item_name = uiXml->ReadAttrib(node, "id", NULL);

			string256 buf;
			xr_sprintf(buf, "id for item don't set, number %d in %s", items_num, xml_file);
			R_ASSERT2(item_name, buf);

			const shared_str id = item_name;
			R_ASSERT3(m_pIdIndex->find(id) == m_pIdIndex->end(), "duplicate item id", item_name);
			m_pIdIndex->emplace(id, u32(m_pItemDataVector->size()));

			ITEM_DATA data;
			data.id = id;
			data.index = index;
			data.node = node;
			data._xml = uiXml;
			m_pItemDataVector->push_back(data);

			index++;
		}
		if (0 == items_num)
			delete_data(uiXml);
	}
}

#undef TEMPLATE_SPECIALIZATION
